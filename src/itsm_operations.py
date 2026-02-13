"""
Módulo de Operaciones ITSM.

Gestiona las operaciones de actualización (PUT) en ITSM para marcar
relaciones como 'Removed'.
"""

from typing import List, Dict, Any, Tuple, Optional
import base64

import requests
import urllib3

from .config import ITSMConfig
from .logger_config import obtener_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


def _crear_headers_itsm(config: Optional[ITSMConfig] = None) -> Dict[str, str]:
    """
    Crea headers de autenticación Basic Auth para ITSM.
    
    Args:
        config: Configuración de ITSM
    
    Returns:
        Dict con headers incluyendo Authorization y Content-Type
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
                verify=False,
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
                    logger.warning(f"Error servidor ITSM ({response.status_code}), reintentando...")
                    continue
                return False, f"Error servidor ITSM después de {max_reintentos} intentos ({response.status_code})"
            
            else:
                logger.error(f"Error HTTP {response.status_code} en ITSM: {response.text[:500]}")
                return False, f"Error HTTP {response.status_code} en ITSM"
        
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en PUT ITSM (intento {intento}/{max_reintentos})")
            if intento == max_reintentos:
                return False, "Timeout en ITSM agotado"
            continue
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Error conexión ITSM (intento {intento}/{max_reintentos}): {e}")
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
    
    Endpoint: PUT /SM/9/rest/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}
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
        logger.error("ERROR CRÍTICO: ITSM_BASE_URL no está configurada en .env")
        logger.error("  Requerida: ITSM_BASE_URL (ej: https://servidor:puerto/SM/9/rest)")
        return None
    
    logger.info(f"ITSM_BASE_URL configurada: {config.BASE_URL}")
    
    if modo_ejecucion == "ejecucion":
        logger.warning("[EJECUCIÓN] Se marcarán relaciones como 'Removed' en ITSM")
    else:
        logger.info("[SIMULACIÓN] Se mostrarán URLs sin ejecutar")
    
    # GARANTÍA: Filtrar solo aquellas que TIENEN ucmdbid_fo válido
    relaciones_validas = [
        item for item in inconsistencias_normales_con_fo 
        if item.get("ucmdbid_fo") and item.get("ucmdbid_fo") != "N/A"
    ]
    
    total = len(relaciones_validas)
    logger.info(f"Total relaciones con relacion_fo VÁLIDA: {total}")
    logger.info("-" * 80)
    
    if not relaciones_validas:
        logger.info("No hay inconsistencias con relacion_fo válida para procesar")
        return None
    
    resumen = []
    exitosas = 0
    fallidas = 0
    
    for idx, item in enumerate(relaciones_validas, 1):
        ucmdbid = item.get("ucmdbId", "").strip()
        ucmdbid_fo = item.get("ucmdbid_fo", "").strip()
        
        if not ucmdbid or not ucmdbid_fo:
            logger.warning(f"[{idx}/{total}] IDs vacíos, saltando")
            continue
        
        # Construcción de URL según spec: /SM/9/rest/cirelationship1to1s/{UcmdbID_fo}/{UcmdbID}
        url = f"{config.BASE_URL}/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}"
        
        logger.info(f"[{idx}/{total}] Procesando: {ucmdbid}")
        logger.debug(f"  ucmdbid_fo: {ucmdbid_fo}")
        logger.debug(f"  URL: {url}")
        
        resultado = {
            "numero": idx,
            "ucmdbId": ucmdbid,
            "ucmdbid_fo": ucmdbid_fo,
            "url": url,
            "metodo": "PUT",
            "body": {"cirelationship1to1": {"status": "Removed"}},
            "modo": "EJECUCION" if modo_ejecucion == "ejecucion" else "SIMULACION",
            "estado": "PENDIENTE",
            "detalles": ""
        }
        
        if modo_ejecucion == "ejecucion":
            exito, mensaje = ejecutar_update_itsm(url, config)
            resultado["estado"] = "EXITOSA" if exito else "FALLIDA"
            resultado["detalles"] = mensaje
            
            if exito:
                exitosas += 1
                logger.info(f"  ✓ PUT {ucmdbid}: {mensaje}")
            else:
                fallidas += 1
                logger.error(f"  ✗ PUT {ucmdbid}: {mensaje}")
        else:
            resultado["estado"] = "SIMULADA"
            logger.info(f"  [SIM] PUT sería ejecutado en ITSM: {url}")
        
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
    """Guarda resumen de operaciones ITSM."""
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
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"[{item['numero']}] {item['metodo']} {item['ucmdbId']}\n")
                f.write(f"  URL: {item['url']}\n")
                f.write(f"  Modo: {item['modo']}\n")
                f.write(f"  Estado: {item['estado']}\n")
                if item['detalles']:
                    f.write(f"  Detalle: {item['detalles']}\n")
                f.write("\n")
        
        logger.info(f"Resumen ITSM guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen ITSM: {e}")
        return None
