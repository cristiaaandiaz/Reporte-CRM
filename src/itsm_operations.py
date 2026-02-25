"""
Módulo de Operaciones ITSM.

Gestiona las operaciones de actualización (PUT) en ITSM para marcar
relaciones como 'Removed'.

Flujo:
    1. GET /rest/Relationships?query=ChildCIs="<end2_id>"&view=expand
       └─> Obtiene ParentCI de la relación
    2. PUT /rest/cirelationship1to1s/{ParentCI}/{end2_id}
       └─> Marca relación como "Removed"
"""

from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import quote
import base64
import time

import requests
import urllib3

from .config import ITSMConfig, VERIFY_SSL
from .logger_config import obtener_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


def consultar_parent_ci_en_itsm(
    end2_id: str,
    config: Optional[ITSMConfig] = None,
    max_reintentos: int = 3,
    delay_reintento: int = 2
) -> Tuple[Optional[str], str]:
    """
    Consulta ITSM para obtener el ParentCI de una relación usando su ChildCI (End2).
    
    Algoritmo de reintento exponencial:
    1. Intenta GET /rest/Relationships?query=ChildCIs="<end2_id>"&view=expand
    2. Si 200 OK:
       a. Extrae ParentCI del JSON (content[0].Relationship.ParentCI)
       b. Retorna (ParentCI, "ParentCI encontrado")
    3. Si 404: Relación no existe
    4. Si 5xx (error servidor):
       a. Reintentos: espera 2^(intento-1) segundos
       b. Mantiene conteo de intentos
       c. Retorna error si se agotan intentos
    5. Si ConnectionError/Timeout:
       a. Similar a 5xx con reintentos automáticos
       b. Registra intentos en log
    
    GET: /rest/Relationships?query=ChildCIs="<end2_id>"&view=expand
    
    Args:
        end2_id: ID del ChildCI (End2)
        config: Configuración de ITSM
        max_reintentos: Máximo número de reintentos (default: 3)
        delay_reintento: Segundos base de espera entre reintentos (default: 2)
        
    Returns:
        Tupla (ParentCI obtenido o None, Mensaje descriptivo)
        Ej: ("Empresas – SDWAN_901999048-9", "ParentCI encontrado: Empresas – SDWAN_901999048-9")
    """
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    if not end2_id or not end2_id.strip():
        logger.error("End2 ID vacío recibido en consultar_parent_ci_en_itsm")
        return None, "End2 ID vacío"
    
    headers = _crear_headers_itsm(config)
    
    # Construir URL de consulta (con URL encoding para caracteres especiales)
    end2_id_encoded = quote(str(end2_id), safe='')
    query = f'ChildCIs="{end2_id_encoded}"'
    url = f"{config.BASE_URL}/Relationships?query={query}&view=expand"
    
    for intento in range(1, max_reintentos + 1):
        try:
            logger.debug(f"[Intento {intento}] GET Relationship: {url}")
            response = requests.get(
                url,
                headers=headers,
                verify=VERIFY_SSL,
                timeout=config.TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Validar estructura de respuesta
                if not isinstance(data, dict):
                    logger.error("Respuesta inválida de ITSM: tipo no es dict")
                    return None, "Respuesta inválida del servidor ITSM"
                
                content = data.get("content", [])
                if not content or not isinstance(content, list):
                    logger.warning(f"No se encontraron relaciones para End2: {end2_id}")
                    return None, f"No encontrada relación con ChildCI={end2_id}"
                
                # Extraer ParentCI del primer elemento
                try:
                    parent_ci = content[0].get("Relationship", {}).get("ParentCI")
                    if not parent_ci:
                        logger.error(f"ParentCI no encontrado en respuesta para End2: {end2_id}")
                        return None, "ParentCI no disponible en la respuesta"
                    
                    logger.debug(f"ParentCI obtenido: {parent_ci}")
                    return parent_ci, f"ParentCI encontrado: {parent_ci}"
                
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"Error extrayendo ParentCI: {e}")
                    return None, f"Error en estructura de datos: {str(e)}"
            
            elif response.status_code == 404:
                logger.warning(f"Relación no encontrada en ITSM para End2: {end2_id}")
                return None, "Relación no encontrada en ITSM (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    espera = delay_reintento * (2 ** (intento - 1))
                    logger.warning(f"Error servidor ITSM ({response.status_code}), reintentando en {espera}s (intento {intento}/{max_reintentos})")
                    time.sleep(espera)
                    continue
                return None, f"Error servidor ITSM después de {max_reintentos} intentos ({response.status_code})"
            
            else:
                logger.error(f"Error HTTP {response.status_code} en GET Relationship: {response.text[:500]}")
                return None, f"Error HTTP {response.status_code} en GET Relationship"
        
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en GET Relationship ITSM (intento {intento}/{max_reintentos})")
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                logger.warning(f"Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
            if intento == max_reintentos:
                return None, "Timeout en GET Relationship agotado"
            continue
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Error conexión ITSM (intento {intento}/{max_reintentos}): {e}")
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                logger.warning(f"Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
            if intento == max_reintentos:
                return None, f"Error de conexión ITSM: {str(e)}"
            continue
        
        except Exception as e:
            logger.error(f"Error inesperado en GET Relationship: {e}")
            return None, f"Error al consultar Relationship: {str(e)}"
    
    return None, "Error desconocido en consulta de Relationship"


def _crear_headers_itsm(config: Optional[ITSMConfig] = None) -> Dict[str, str]:
    """
    Crea headers de autenticación Basic Auth para ITSM.
    
    Algoritmo:
    1. Obtiene config de ITSM (parámetro o config global)
    2. Concatena USERNAME:PASSWORD
    3. Codifica Base64: base64(username:password)
    4. Crea header Authorization: "Basic <encoded>"
    5. Retorna dict con Authorization y Content-Type: application/json
    
    Seguridad:
    - Las credenciales no se escriben en logs
    - Usa encoding/decoding estándar IETF RFC 7617 Basic Auth
    - VERIFY_SSL debe estar habilitado en producción
    
    Args:
        config: Configuración de ITSM (si None, usa itsm_config global)
    
    Returns:
        Dict con headers incluyendo:
        - Authorization: "Basic <base64(username:password)>"
        - Content-Type: "application/json"
        
    Ejemplo:
        >>> headers = _crear_headers_itsm()
        >>> headers["Authorization"]  # "Basic dXNlcjpwYXNz"
    """
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    credenciales = f"{config.USERNAME}:{config.PASSWORD}"
    credenciales_encoded = base64.b64encode(credenciales.encode()).decode()
    
    return {
        "Authorization": f"Basic {credenciales_encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def ejecutar_update_itsm(
    url: str,
    config: Optional[ITSMConfig] = None,
    max_reintentos: int = 3,
    delay_reintento: int = 2
) -> Tuple[bool, str]:
    """
    Ejecuta PUT en ITSM con reintentos automáticos para marcar relaciones como 'Removed'.
    
    Args:
        url: URL completa del endpoint PUT en ITSM
        config: Configuración de ITSM
        max_reintentos: Máximo número de reintentos
        delay_reintento: Segundos de espera entre reintentos
        
    Returns:
        Tupla (Éxito, Mensaje descriptivo)
    """
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    if not url or not url.strip():
        logger.error("URL vacía recibida en ejecutar_update_itsm")
        return False, "URL vacía"
    
    headers = _crear_headers_itsm(config)
    payload = {
        "cirelationship1to1": {
            "status": "Removed"
        }
    }
    
    for intento in range(1, max_reintentos + 1):
        try:
            response = requests.put(
                url,
                json=payload,
                headers=headers,
                verify=VERIFY_SSL,
                timeout=config.TIMEOUT
            )
            
            if response.status_code in [200, 204]:
                logger.debug(f"PUT exitoso en ITSM: {response.status_code}")
                return True, f"Actualización exitosa en ITSM (HTTP {response.status_code})"
            
            elif response.status_code == 404:
                logger.warning(f"Relación no encontrada en ITSM: {url}")
                return False, "Relación no encontrada en ITSM (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    espera = delay_reintento * (2 ** (intento - 1))  # Backoff exponencial
                    logger.warning(f"Error servidor ITSM ({response.status_code}), reintentando en {espera}s (intento {intento}/{max_reintentos})")
                    time.sleep(espera)
                    continue
                return False, f"Error servidor ITSM después de {max_reintentos} intentos ({response.status_code})"
            
            else:
                logger.error(f"Error HTTP {response.status_code} en ITSM: {response.text[:500]}")
                return False, f"Error HTTP {response.status_code} en ITSM"
        
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en PUT ITSM (intento {intento}/{max_reintentos})")
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                logger.warning(f"Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
            if intento == max_reintentos:
                return False, "Timeout en ITSM agotado"
            continue
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Error conexión ITSM (intento {intento}/{max_reintentos}): {e}")
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                logger.warning(f"Esperando {espera}s antes de reintentar...")
                time.sleep(espera)
            if intento == max_reintentos:
                return False, f"Error de conexión ITSM: {str(e)}"
            continue
        
        except Exception as e:
            logger.error(f"Error inesperado en PUT ITSM: {e}")
            return False, f"Error ITSM: {str(e)}"
    
    return False, "Error desconocido en ITSM"


def eliminar_en_itsm(
    inconsistencias_normales_con_fo: List[Dict[str, Any]],
    carpeta: Any,
    config: Optional[ITSMConfig] = None,
    modo_ejecucion: str = "simulacion",
    generar_resumen: bool = True
) -> None:
    """
    Procesa actualizaciones en ITSM SOLO para relaciones con relacion_fo: true.
    
    Proceso en dos pasos:
    1. GET /SM/9/rest/Relationships?query=ChildCIs="<end2Id>"&view=expand → obtener ParentCI
    2. PUT /SM/9/rest/cirelationship1to1s/{ParentCI}/{end2Id} → marcar como Removed
    
    Body: {"cirelationship1to1": {"status": "Removed"}}
    
    Args:
        inconsistencias_normales_con_fo: Lista de relaciones con fo:true
        carpeta: Ruta para guardar resumen
        config: Configuración de ITSM
        modo_ejecucion: "simulacion" o "ejecucion"
        generar_resumen: True para generar archivo de resumen
    """
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    logger.info("=" * 80)
    logger.info("PASO 6B: ACTUALIZAR EN ITSM (Sistema de Gestión de Servicios TI)")
    logger.info("=" * 80)
    
    if not config.BASE_URL:
        logger.error("ERROR CRÍTICO: ITSM_URL no está configurada en .env")
        logger.error("  Requerida: ITSM_URL (ej: https://servidor:puerto/SM/9/rest)")
        return None
    
    logger.info(f"ITSM_URL configurada: {config.BASE_URL}")
    
    if modo_ejecucion == "ejecucion":
        logger.warning("[EJECUCIÓN] Se consultarán y marcarán relaciones como 'Removed' en ITSM")
    else:
        logger.info("[SIMULACIÓN] Se mostrarán URLs sin ejecutar")
    
    # GARANTÍA: Filtrar solo aquellas que TIENEN end2Id válido
    relaciones_validas = [
        item for item in inconsistencias_normales_con_fo 
        if item.get("end2Id") and item.get("end2Id") != "N/A"
    ]
    
    total = len(relaciones_validas)
    logger.info(f"Total relaciones para procesar: {total}")
    logger.info("-" * 80)
    
    if not relaciones_validas:
        logger.info("No hay inconsistencias para procesar")
        return None
    
    resumen = []
    exitosas = 0
    fallidas = 0
    
    for idx, item in enumerate(relaciones_validas, 1):
        end2id = item.get("end2Id", "").strip()
        ucmdbid = item.get("ucmdbId", "").strip()
        nit_end1 = item.get("nit_end1", "N/A")
        nit_end2 = item.get("nit_end2", "N/A")
        end1id = item.get("end1Id", "N/A")
        label_end1 = item.get("display_label_end1", "N/A")
        label_end2 = item.get("display_label_end2", "N/A")
        
        if not end2id:
            logger.warning(f"[{idx}/{total}] End2 ID vacío, saltando")
            continue
        
        # Mostrar resumen en formato legible
        logger.info(f"[{idx}/{total}] Procesando relación: {ucmdbid}")
        logger.info(f"  NIT: {nit_end1} ≠ {nit_end2}")
        logger.info(f"  End1: {label_end1} ({end1id})")
        logger.info(f"  End2: {label_end2} ({end2id})")
        
        resultado = {
            "numero": idx,
            "ucmdbId": ucmdbid,
            "end2Id": end2id,
            "parentCI": None,
            "url_query": f"{config.BASE_URL}/Relationships?query=ChildCIs=\"{quote(str(end2id), safe='')}\"&view=expand",
            "url_delete": None,
            "metodo": "GET + PUT",
            "modo": "EJECUCION" if modo_ejecucion == "ejecucion" else "SIMULACION",
            "estado": "PENDIENTE",
            "detalles": ""
        }
        
        # PASO 1: Consultar ParentCI usando GET (en AMBOS modos)
        logger.info("  → Paso 1: GET Relationship para obtener ParentCI...")
        parent_ci, msg_consulta = consultar_parent_ci_en_itsm(end2id, config)
        
        if not parent_ci:
            resultado["estado"] = "FALLIDA"
            resultado["detalles"] = f"GET Relationship falló: {msg_consulta}"
            fallidas += 1
            logger.error(f"  ✗ Consulta GET falló: {msg_consulta}")
            resumen.append(resultado)
            continue
        
        resultado["parentCI"] = parent_ci
        logger.info(f"  ✓ ParentCI obtenido: {parent_ci}")
        
        # PASO 2: Construir URL de eliminación con ParentCI (con URL encoding)
        # ParentCI puede tener espacios y caracteres especiales, necesita encoding
        parent_ci_encoded = quote(str(parent_ci), safe='')
        end2id_encoded = quote(str(end2id), safe='')
        delete_url = f"{config.BASE_URL}/cirelationship1to1s/{parent_ci_encoded}/{end2id_encoded}"
        resultado["url_delete"] = delete_url
        
        if modo_ejecucion == "ejecucion":
            logger.info("  → Paso 2: PUT para marcar como 'Removed'...")
            exito, msg_delete = ejecutar_update_itsm(delete_url, config)
            resultado["estado"] = "EXITOSA" if exito else "FALLIDA"
            resultado["detalles"] = msg_delete
            
            if exito:
                exitosas += 1
                logger.info("  ✓ HTTP 200 OK - status: Removed")
            else:
                fallidas += 1
                logger.error(f"  ✗ PUT falló: {msg_delete}")
        else:
            # SIMULACIÓN: Mostrar URLs que se ejecutarían
            resultado["estado"] = "SIMULADA"
            logger.info(f"  [SIM] PUT {delete_url}")
        
        resumen.append(resultado)
    
    logger.info("-" * 80)
    logger.info("Resumen ITSM:")
    logger.info(f"  Total procesadas: {total}")
    logger.info(f"  Exitosas: {exitosas}")
    logger.info(f"  Fallidas: {fallidas}")
    if modo_ejecucion != "ejecucion":
        logger.info(f"  Simuladas: {total}")
    
    if generar_resumen:
        _guardar_resumen_itsm(resumen, carpeta)


def _guardar_resumen_itsm(
    resumen: List[Dict[str, Any]],
    carpeta: Any
) -> Optional[Any]:
    """Guarda resumen de operaciones ITSM con detalles de consulta y eliminación."""
    from pathlib import Path
    
    if not isinstance(carpeta, Path):
        carpeta = Path(carpeta)
    
    if carpeta.name == "disabled":
        logger.info("Guardado de resumen ITSM deshabilitado")
        return None
    
    archivo = carpeta / "resumen_itsm.txt"
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("RESUMEN DE OPERACIONES ITSM\n")
            f.write("Proceso: GET Relationship → Obtener ParentCI → PUT cirelationship1to1s\n")
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"[{item['numero']}] Relación: {item['ucmdbId']}\n")
                f.write(f"  End2 ID: {item['end2Id']}\n")
                
                if item['parentCI']:
                    f.write(f"  ParentCI obtenido: {item['parentCI']}\n")
                
                f.write("\n  PASO 1 (GET Relationship):\n")
                f.write(f"    URL: {item['url_query']}\n")
                
                if item['url_delete']:
                    f.write("\n  PASO 2 (PUT cirelationship1to1s):\n")
                    f.write(f"    URL: {item['url_delete']}\n")
                
                f.write(f"\n  Metodo: {item['metodo']}\n")
                f.write(f"  Modo: {item['modo']}\n")
                f.write(f"  Estado: {item['estado']}\n")
                
                if item['detalles']:
                    f.write(f"  Detalle: {item['detalles']}\n")
                
                f.write("\n" + "-" * 80 + "\n\n")
        
        logger.info(f"Resumen ITSM guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen ITSM: {e}")
        return None
