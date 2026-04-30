"""
Operaciones PUT en ITSM para marcar relaciones como 'Removed'.
"""

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
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
    """Consulta ITSM para obtener el ParentCI usando el ChildCI (End2)."""
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    if not end2_id or not end2_id.strip():
        return None, "End2 ID vacío"
    
    headers = _crear_headers_itsm(config)
    
    end2_id_encoded = quote(str(end2_id), safe='')
    query = f'ChildCIs="{end2_id_encoded}"'
    url = f"{config.BASE_URL}/Relationships?query={query}&view=expand"
    
    for intento in range(1, max_reintentos + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                verify=VERIFY_SSL,
                timeout=config.TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", [])
                
                if not content or not isinstance(content, list):
                    return None, f"No encontrada relación con ChildCI={end2_id}"
                
                try:
                    parent_ci = content[0].get("Relationship", {}).get("ParentCI")
                    if not parent_ci:
                        return None, "ParentCI no disponible en respuesta"
                    
                    return parent_ci, f"ParentCI: {parent_ci}"
                
                except (KeyError, IndexError, TypeError) as e:
                    return None, f"Error extrayendo ParentCI: {e}"
            
            elif response.status_code == 404:
                return None, "Relación no encontrada (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    espera = delay_reintento * (2 ** (intento - 1))
                    logger.warning(f"Error ITSM {response.status_code}, reintento en {espera}s")
                    time.sleep(espera)
                    continue
                return None, f"Error servidor después de {max_reintentos} intentos"
            
            else:
                return None, f"Error HTTP {response.status_code}"
        
        except requests.exceptions.Timeout:
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                time.sleep(espera)
            if intento == max_reintentos:
                return None, "Timeout agotado"
        
        except requests.exceptions.ConnectionError as e:
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                time.sleep(espera)
            if intento == max_reintentos:
                return None, f"Error de conexión: {e}"
        
        except Exception as e:
            return None, f"Error: {e}"
    
    return None, "Error desconocido"


def _crear_headers_itsm(config: Optional[ITSMConfig] = None) -> Dict[str, str]:
    """Crea headers con autenticación Basic Auth para ITSM."""
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
    """Ejecuta PUT en ITSM para marcar relaciones como 'Removed'."""
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    if not url or not url.strip():
        return False, "URL vacía"
    
    headers = _crear_headers_itsm(config)
    payload = {"cirelationship1to1": {"status": "Removed"}}
    
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
                return True, f"Actualizado (HTTP {response.status_code})"
            
            elif response.status_code == 404:
                return False, "Relación no encontrada (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    espera = delay_reintento * (2 ** (intento - 1))
                    time.sleep(espera)
                    continue
                return False, f"Error servidor después de {max_reintentos} intentos"
            
            else:
                return False, f"Error HTTP {response.status_code}"
        
        except requests.exceptions.Timeout:
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                time.sleep(espera)
            if intento == max_reintentos:
                return False, "Timeout en ITSM"
        
        except requests.exceptions.ConnectionError as e:
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                time.sleep(espera)
            if intento == max_reintentos:
                return False, f"Error de conexión: {e}"
        
        except Exception as e:
            return False, f"Error: {e}"
    
    return False, "Error desconocido"


def eliminar_en_itsm(
    inconsistencias_normales_con_fo: List[Dict[str, Any]],
    carpeta: Any,
    config: Optional[ITSMConfig] = None,
    modo_ejecucion: str = "simulacion",
    generar_resumen: bool = True,
    cis_by_id: Optional[Dict[str, Any]] = None
) -> None:
    """Procesa actualizaciones en ITSM para relaciones con relacion_fo=true."""
    if config is None:
        from .config import itsm_config
        config = itsm_config
    
    logger.info("=" * 80)
    logger.info("PASO 6C: ACTUALIZAR EN ITSM")
    logger.info("=" * 80)
    
    if not config.BASE_URL:
        logger.error("ITSM_URL no configurada en .env")
        return
    
    logger.info(f"ITSM_URL: {config.BASE_URL}")
    logger.info(f"Modo: {'EJECUCIÓN' if modo_ejecucion == 'ejecucion' else 'SIMULACIÓN'}")
    
    relaciones_validas = [
        item for item in inconsistencias_normales_con_fo 
        if item.get("end2Id") and item.get("end2Id") != "N/A"
    ]
    
    total = len(relaciones_validas)
    logger.info(f"Total relaciones: {total}")
    
    if not relaciones_validas:
        logger.info("No hay relaciones para procesar")
        return None
    
    resumen: List[Dict[str, Any]] = []
    exitosas = 0
    fallidas = 0
    
    def obtener_display_label(ucmdb_id: str) -> str:
        if cis_by_id and ucmdb_id in cis_by_id:
            ci = cis_by_id[ucmdb_id]
            props = ci.get("properties", {})
            if props.get("display_label"):
                return props.get("display_label")
            if ci.get("label"):
                return ci.get("label")
        return "N/A"
    
    for idx, item in enumerate(relaciones_validas, 1):
        end2id = item.get("end2Id", "").strip()
        ucmdbid = item.get("ucmdbId", "").strip()
        
        if not end2id:
            continue
        
        logger.info(f"[{idx}/{total}] Procesando: {ucmdbid}")
        logger.info(f"  NIT: {item.get('nit_end1', 'N/A')} ≠ {item.get('nit_end2', 'N/A')}")
        logger.info(f"  End1: {item.get('display_label_end1', 'N/A')}")
        logger.info(f"  End2: {item.get('display_label_end2', 'N/A')}")
        
        resultado: Dict[str, Any] = {
            "numero": idx,
            "ucmdbId": ucmdbid,
            "end2Id": end2id,
            "display_label_end1": item.get("display_label_end1", "N/A"),
            "display_label_end2": item.get("display_label_end2", "N/A"),
            "display_label_end2_obtenido": obtener_display_label(end2id),
            "parentCI": None,
            "url_query": f"{config.BASE_URL}/Relationships?query=ChildCIs=\"{quote(str(end2id), safe='')}\"&view=expand",
            "url_delete": None,
            "metodo": "GET + PUT",
            "modo": "EJECUCION" if modo_ejecucion == "ejecucion" else "SIMULACION",
            "estado": "PENDIENTE",
            "detalles": ""
        }
        
        logger.info("  → Paso 1: GET Relationship para obtener ParentCI...")
        parent_ci, msg_consulta = consultar_parent_ci_en_itsm(end2id, config)
        
        if not parent_ci:
            resultado["estado"] = "FALLIDA"
            resultado["detalles"] = f"GET falló: {msg_consulta}"
            fallidas += 1
            logger.error(f"  ✗ GET falló: {msg_consulta}")
            resumen.append(resultado)
            continue
        
        resultado["parentCI"] = parent_ci
        logger.info(f"  ✓ ParentCI: {parent_ci}")
        
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
            resultado["estado"] = "SIMULADA"
            logger.info(f"  [SIM] PUT {delete_url}")
        
        resumen.append(resultado)
    
    logger.info(f"Total procesadas: {total}, Exitosas: {exitosas}, Fallidas: {fallidas}")
    
    if generar_resumen:
        _guardar_resumen_itsm(resumen, carpeta)


def _guardar_resumen_itsm(resumen: List[Dict[str, Any]], carpeta: Any) -> Optional[Path]:
    """Guarda resumen de operaciones ITSM."""
    from pathlib import Path
    
    if not isinstance(carpeta, Path):
        carpeta = Path(carpeta)
    
    if carpeta.name == "disabled":
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
                f.write(f"  Display Label End2: {item.get('display_label_end2', 'N/A')}\n")
                if item['parentCI']:
                    f.write(f"  ParentCI: {item['parentCI']}\n")
                f.write(f"  GET URL: {item['url_query']}\n")
                if item['url_delete']:
                    f.write(f"  PUT URL: {item['url_delete']}\n")
                f.write(f"  Modo: {item['modo']}\n")
                f.write(f"  Estado: {item['estado']}\n")
                if item['detalles']:
                    f.write(f"  Detalle: {item['detalles']}\n")
                f.write("\n" + "-" * 80 + "\n\n")
        
        logger.info(f"Resumen ITSM guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen: {e}")
        return None