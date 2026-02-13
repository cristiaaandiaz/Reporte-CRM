"""
Módulo de Operaciones UCMDB.

Gestiona las operaciones de eliminación (DELETE) en UCMDB.
"""

from typing import List, Dict, Any, Tuple, Optional
import base64

import requests
import urllib3

from .config import UCMDBConfig
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
    """
    Ejecuta DELETE en UCMDB con reintentos automáticos.
    
    Args:
        url: URL completa del endpoint DELETE en UCMDB
        token: Token JWT para autenticación
        config: Configuración de UCMDB
        max_reintentos: Máximo número de reintentos
        delay_reintento: Segundos de espera entre reintentos
        
    Returns:
        Tupla (Éxito, Mensaje descriptivo)
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    for intento in range(1, max_reintentos + 1):
        try:
            response = requests.delete(
                url,
                headers=headers,
                verify=False,
                timeout=config.REQUEST_TIMEOUT
            )
            
            if response.status_code in [200, 204]:
                logger.debug(f"DELETE exitoso: {response.status_code}")
                return True, f"Eliminación exitosa (HTTP {response.status_code})"
            
            elif response.status_code == 404:
                logger.warning(f"Recurso no encontrado: {url}")
                return False, "Recurso no encontrado (HTTP 404)"
            
            elif response.status_code in [500, 502, 503, 504]:
                if intento < max_reintentos:
                    logger.warning(f"Error servidor ({response.status_code}), reintentando...")
                    continue
                return False, f"Error servidor después de {max_reintentos} intentos ({response.status_code})"
            
            else:
                logger.error(f"Error HTTP {response.status_code}: {response.text[:500]}")
                return False, f"Error HTTP {response.status_code}"
        
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en DELETE (intento {intento}/{max_reintentos})")
            if intento == max_reintentos:
                return False, "Timeout agotado"
            continue
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Error conexión (intento {intento}/{max_reintentos}): {e}")
            if intento == max_reintentos:
                return False, f"Error de conexión: {str(e)}"
            continue
        
        except Exception as e:
            logger.error(f"Error inesperado en DELETE: {e}")
            return False, f"Error: {str(e)}"
    
    return False, "Error desconocido"


def eliminar_en_ucmdb(
    token: str,
    inconsistencias: List[Dict[str, Any]],
    carpeta: Any,
    config: Optional[UCMDBConfig] = None,
    modo_ejecucion: str = "simulacion",
    generar_resumen: bool = True
) -> Optional[Any]:
    """
    Procesa eliminaciones en UCMDB para TODAS las relaciones normales.
    
    Para cada relación:
    - SI relacion_fo = true: Elimina AMBOS ucmdbId + ucmdbid_fo (2 DELETE calls)
    - SI relacion_fo = false: Elimina SOLO ucmdbId (1 DELETE call)
    
    Args:
        token: Token JWT de autenticación UCMDB
        inconsistencias: Lista de ALL relaciones normales
        carpeta: Ruta para guardar resumen
        config: Configuración de UCMDB
        modo_ejecucion: "simulacion" o "ejecucion"
        generar_resumen: True para generar archivo de resumen
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    logger.info("=" * 80)
    logger.info("PASO 6A: ELIMINAR EN UCMDB")
    logger.info("=" * 80)
    
    if modo_ejecucion == "ejecucion" and not token:
        logger.error("ERROR CRÍTICO: Se requiere token para ejecución real")
        return None
    
    if modo_ejecucion == "ejecucion":
        logger.warning("[EJECUCIÓN] Se eliminarán relaciones REALMENTE en UCMDB")
    else:
        logger.info("[SIMULACIÓN] Se mostrarán URLs sin ejecutar")
    
    total = len(inconsistencias)
    logger.info(f"Total de relaciones a procesar: {total}")
    logger.info("-" * 80)
    
    if not inconsistencias:
        logger.info("No hay inconsistencias para procesar")
        return None
    
    exitosas = 0
    fallidas = 0
    total_deletes = 0
    resumen = []
    
    for idx, item in enumerate(inconsistencias, 1):
        ucmdbid = item.get("ucmdbId", "").strip()
        ucmdbid_fo = item.get("ucmdbid_fo", "N/A")
        relacion_fo = item.get("relacion_fo", False)
        nit_end1 = item.get("nit_end1", "N/A")
        nit_end2 = item.get("nit_end2", "N/A")
        end1id = item.get("end1Id", "N/A")
        end2id = item.get("end2Id", "N/A")
        label_end1 = item.get("display_label_end1", "N/A")
        label_end2 = item.get("display_label_end2", "N/A")
        
        if not ucmdbid:
            logger.warning(f"[{idx}/{total}] ucmdbId vacío, saltando")
            continue
        
        # Mostrar resumen en formato legible
        logger.info(f"[{idx}/{total}] DELETE - Relación: {ucmdbid}")
        logger.info(f"  FO: {relacion_fo} ({ucmdbid_fo}) | NIT: {nit_end1} ≠ {nit_end2}")
        logger.info(f"  End1: {label_end1} ({end1id})")
        logger.info(f"  End2: {label_end2} ({end2id})")
        
        # Lista de IDs a eliminar
        ids_a_eliminar = [ucmdbid]
        if relacion_fo and ucmdbid_fo != "N/A":
            ids_a_eliminar.append(ucmdbid_fo)
        
        for ucmdb_id in ids_a_eliminar:
            total_deletes += 1
            url = f"{config.DELETE_ENDPOINT}/{ucmdb_id}"
            
            resultado = {
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
                    logger.info(f"  ✓ HTTP 204 OK - {ucmdb_id}")
                else:
                    fallidas += 1
                    logger.error(f"  ✗ ERROR - {ucmdb_id}: {mensaje}")
            else:
                resultado["estado"] = "SIMULADA"
                logger.info(f"  [SIM] DELETE {url}")
                if relacion_fo and ucmdbid_fo != "N/A" and ucmdb_id == ucmdbid_fo:
                    logger.info(f"       + Relación FO también se eliminaría: {ucmdbid}")
            
            resumen.append(resultado)
    
    logger.info("-" * 80)
    logger.info("Resumen UCMDB:")
    logger.info(f"  Total relaciones procesadas: {total}")
    logger.info(f"  Total DELETE requests: {total_deletes}")
    
    if modo_ejecucion == "ejecucion":
        logger.info(f"  Exitosas: {exitosas}")
        logger.info(f"  Fallidas: {fallidas}")
    else:
        logger.info(f"  Simuladas: {total_deletes}")
    
    if generar_resumen:
        _guardar_resumen_ucmdb(resumen, carpeta)
    
    return resumen


def _guardar_resumen_ucmdb(
    resumen: List[Dict[str, Any]],
    carpeta: Any
) -> Optional[Any]:
    """Guarda resumen de operaciones UCMDB."""
    from pathlib import Path
    
    if not isinstance(carpeta, Path):
        carpeta = Path(carpeta)
    
    if carpeta.name == "disabled":
        logger.info("Guardado de resumen UCMDB deshabilitado")
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
        logger.error(f"Error guardando resumen UCMDB: {e}")
        return None
