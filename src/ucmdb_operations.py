"""
Operaciones DELETE en UCMDB.
"""

from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import time

import requests
import urllib3

from .config import UCMDBConfig, VERIFY_SSL
from .logger_config import obtener_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


def ejecutar_delete_ucmdb(
    url: str,
    token: str,
    config: Optional[UCMDBConfig] = None,
    max_reintentos: int = 3,
    delay_reintento: int = 2
) -> Tuple[bool, str]:
    """Ejecuta DELETE en UCMDB con reintentos."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    headers = {"Authorization": f"Bearer {token}"}
    
    for intento in range(1, max_reintentos + 1):
        try:
            response = requests.delete(
                url,
                headers=headers,
                verify=VERIFY_SSL,
                timeout=config.REQUEST_TIMEOUT
            )
            
            if response.status_code in [200, 204]:
                return True, f"Eliminado (HTTP {response.status_code})"
            
            elif response.status_code == 404:
                return False, "No encontrado (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    espera = delay_reintento * (2 ** (intento - 1))
                    logger.warning(f"Error {response.status_code}, reintento en {espera}s")
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
                return False, "Timeout agotado"
        
        except requests.exceptions.ConnectionError as e:
            if intento < max_reintentos:
                espera = delay_reintento * (2 ** (intento - 1))
                time.sleep(espera)
            if intento == max_reintentos:
                return False, f"Error de conexión: {e}"
        
        except Exception as e:
            return False, f"Error: {e}"
    
    return False, "Error desconocido"


def eliminar_en_ucmdb(
    token: str,
    inconsistencias: List[Dict[str, Any]],
    carpeta: Any,
    config: Optional[UCMDBConfig] = None,
    modo_ejecucion: str = "simulacion",
    generar_resumen: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """Procesa eliminaciones en UCMDB para relaciones normales."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    logger.info("=" * 80)
    logger.info("PASO 6A: ELIMINAR EN UCMDB")
    logger.info("=" * 80)
    
    if modo_ejecucion == "ejecucion" and not token:
        logger.error("Se requiere token para ejecución real")
        return None
    
    logger.info(f"Modo: {'EJECUCIÓN' if modo_ejecucion == 'ejecucion' else 'SIMULACIÓN'}")
    logger.info(f"Total de relaciones: {len(inconsistencias)}")
    
    if not inconsistencias:
        logger.info("No hay inconsistencias para procesar")
        return None
    
    exitosas = 0
    fallidas = 0
    total_deletes = 0
    resumen: List[Dict[str, Any]] = []
    
    for idx, item in enumerate(inconsistencias, 1):
        ucmdbid = item.get("ucmdbId", "").strip()
        ucmdbid_fo = item.get("ucmdbid_fo", "N/A")
        relacion_fo = item.get("relacion_fo", False)
        nit_end1 = item.get("nit_end1", "N/A")
        nit_end2 = item.get("nit_end2", "N/A")
        label_end1 = item.get("display_label_end1", "N/A")
        label_end2 = item.get("display_label_end2", "N/A")
        
        if not ucmdbid:
            continue
        
        logger.info(f"[{idx}/{len(inconsistencias)}] DELETE - {ucmdbid}")
        logger.info(f"  FO: {relacion_fo} | NIT: {nit_end1} ≠ {nit_end2}")
        logger.info(f"  End1: {label_end1}")
        logger.info(f"  End2: {label_end2}")
        
        ids_a_eliminar = [ucmdbid]
        if relacion_fo and ucmdbid_fo != "N/A":
            ids_a_eliminar.append(ucmdbid_fo)
        
        for ucmdb_id in ids_a_eliminar:
            total_deletes += 1
            url = f"{config.DELETE_ENDPOINT}/{ucmdb_id}"
            
            resultado: Dict[str, Any] = {
                "numero": total_deletes,
                "ucmdbId": ucmdb_id,
                "url": url,
                "metodo": "DELETE",
                "modo": "EJECUCION" if modo_ejecucion == "ejecucion" else "SIMULACION",
                "estado": "PENDIENTE",
                "detalles": ""
            }
            
            if modo_ejecucion == "ejecucion":
                exito, mensaje = ejecutar_delete_ucmdb(url, token, config)
                resultado["estado"] = "EXITOSA" if exito else "FALLIDA"
                resultado["detalles"] = mensaje
                
                if exito:
                    exitosas += 1
                    logger.info(f"  ✓ {ucmdb_id}")
                else:
                    fallidas += 1
                    logger.error(f"  ✗ {ucmdb_id}: {mensaje}")
            else:
                resultado["estado"] = "SIMULADA"
                logger.info(f"  [SIM] DELETE {url}")
                if relacion_fo and ucmdbid_fo != "N/A" and ucmdb_id == ucmdbid_fo:
                    logger.info("       → (Registro FO)")
            
            resumen.append(resultado)
    
    logger.info(f"Total DELETE requests: {total_deletes}")
    if modo_ejecucion == "ejecucion":
        logger.info(f"Exitosas: {exitosas}, Fallidas: {fallidas}")
    else:
        logger.info(f"Simuladas: {total_deletes}")
    
    if generar_resumen:
        _guardar_resumen_ucmdb(resumen, carpeta)
    
    return resumen


def _guardar_resumen_ucmdb(resumen: List[Dict[str, Any]], carpeta: Any) -> Optional[Path]:
    """Guarda resumen de operaciones UCMDB."""
    from pathlib import Path
    
    if not isinstance(carpeta, Path):
        carpeta = Path(carpeta)
    
    if carpeta.name == "disabled":
        return None
    
    archivo = carpeta / "resumen_ucmdb.txt"
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("RESUMEN DE OPERACIONES UCMDB\n")
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"[{item['numero']}] {item['metodo']} {item['ucmdbId']}\n")
                f.write(f"  URL: {item['url']}\n")
                f.write(f"  Modo: {item['modo']}\n")
                f.write(f"  Estado: {item['estado']}\n")
                if item['detalles']:
                    f.write(f"  Detalle: {item['detalles']}\n")
                f.write("\n")
        
        logger.info(f"Resumen UCMDB guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen: {e}")
        return None


def eliminar_relaciones_usage_de_servicecodes(
    token: str,
    relaciones_usage: List[Dict[str, Any]],
    carpeta: Any,
    config: Optional[UCMDBConfig] = None,
    modo_ejecucion: str = "simulacion",
    generar_resumen: bool = True
) -> Optional[List[Dict[str, Any]]]:
    """Procesa eliminaciones de relaciones usage en UCMDB."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    logger.info("=" * 80)
    logger.info("PASO 6B: ELIMINAR RELACIONES USAGE EN UCMDB")
    logger.info("=" * 80)
    
    if modo_ejecucion == "ejecucion" and not token:
        logger.error("Se requiere token para ejecución real")
        return None
    
    logger.info(f"Modo: {'EJECUCIÓN' if modo_ejecucion == 'ejecucion' else 'SIMULACIÓN'}")
    logger.info(f"Total de relaciones usage: {len(relaciones_usage)}")
    
    if not relaciones_usage:
        logger.info("No hay relaciones usage para procesar")
        return None
    
    exitosas = 0
    fallidas = 0
    no_encontradas = 0
    resumen: List[Dict[str, Any]] = []
    
    for idx, item in enumerate(relaciones_usage, 1):
        ucmdbid = item.get("ucmdbId", "").strip()
        
        if not ucmdbid:
            continue
        
        logger.info(f"[{idx}/{len(relaciones_usage)}] DELETE - {ucmdbid}")
        logger.info(f"  App: {item.get('display_label_end1', 'N/A')}")
        logger.info(f"  Servicecode: {item.get('display_label_end2', 'N/A')}")
        
        url = f"{config.DELETE_ENDPOINT}/{ucmdbid}"
        
        resultado: Dict[str, Any] = {
            "numero": idx,
            "ucmdbId": ucmdbid,
            "url": url,
            "metodo": "DELETE",
            "tipo_relacion": item.get("type", "usage"),
            "end1_label": item.get("display_label_end1", "N/A"),
            "end2_label": item.get("display_label_end2", "N/A"),
            "modo": "EJECUCION" if modo_ejecucion == "ejecucion" else "SIMULACION",
            "estado": "PENDIENTE",
            "detalles": ""
        }
        
        if modo_ejecucion == "ejecucion":
            exito, mensaje = ejecutar_delete_ucmdb(url, token, config)
            
            if exito:
                resultado["estado"] = "EXITOSA"
                exitosas += 1
                logger.info(f"  ✓ {ucmdbid}")
            else:
                if "404" in mensaje:
                    resultado["estado"] = "NO_ENCONTRADA"
                    no_encontradas += 1
                else:
                    resultado["estado"] = "FALLIDA"
                    fallidas += 1
                logger.error(f"  ✗ {ucmdbid}: {mensaje}")
                resultado["detalles"] = mensaje
        else:
            resultado["estado"] = "SIMULADA"
            logger.info(f"  [SIM] DELETE {url}")
        
        resumen.append(resultado)
    
    logger.info(f"Total procesadas: {len(relaciones_usage)}")
    if modo_ejecucion == "ejecucion":
        logger.info(f"Exitosas: {exitosas}, Fallidas: {fallidas}, No encontradas: {no_encontradas}")
    else:
        logger.info(f"Simuladas: {len(relaciones_usage)}")
    
    if generar_resumen:
        _guardar_resumen_usage(resumen, carpeta)
    
    return resumen


def _guardar_resumen_usage(resumen: List[Dict[str, Any]], carpeta: Any) -> Optional[Path]:
    """Guarda resumen de operaciones de eliminación usage."""
    from pathlib import Path
    
    if not isinstance(carpeta, Path):
        carpeta = Path(carpeta)
    
    if carpeta.name == "disabled":
        return None
    
    archivo = carpeta / "resumen_eliminacion_usage.txt"
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("RESUMEN DE ELIMINACIÓN DE RELACIONES USAGE\n")
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"[{item['numero']}] {item['metodo']} {item['ucmdbId']}\n")
                f.write(f"  URL: {item['url']}\n")
                f.write(f"  Tipo: {item.get('tipo_relacion', 'N/A')}\n")
                f.write(f"  Aplicación: {item.get('end1_label', 'N/A')}\n")
                f.write(f"  Servicecode: {item.get('end2_label', 'N/A')}\n")
                f.write(f"  Modo: {item['modo']}\n")
                f.write(f"  Estado: {item['estado']}\n")
                if item['detalles']:
                    f.write(f"  Detalle: {item['detalles']}\n")
                f.write("\n")
        
        logger.info(f"Resumen usage guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen: {e}")
        return None