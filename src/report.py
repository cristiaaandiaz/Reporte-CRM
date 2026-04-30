"""
Consultas a UCMDB API y validación de NITs.
"""

import json
import time
import socket
from typing import Optional, Dict, List, Any, Tuple
from io import BytesIO

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as Urllib3Retry

from .config import UCMDBConfig, ReportConfig, VERIFY_SSL
from .logger_config import obtener_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


class HTTPAdapterWithSocketKeepalive(HTTPAdapter):
    """HTTPAdapter con socket keep-alive para conexiones largas."""
    
    def init_poolmanager(self, *args, **kwargs):
        kwargs["socket_options"] = [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
            (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        ]
        return super().init_poolmanager(*args, **kwargs)


class ReportTimeoutError(Exception):
    """Excepción para timeouts en consulta de reportes."""
    pass


class ReportError(Exception):
    """Excepción general para errores en reportes."""
    pass


def consultar_reporte_ucmdb(
    token: str,
    config: Optional[UCMDBConfig] = None,
    timeout_override: Optional[tuple[int, int]] = None,
    reintentos: Optional[int] = None
) -> Optional[str]:
    """Consulta el reporte JSON desde UCMDB."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    reintentos = reintentos or config.MAX_RETRIES
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": config.CONTENT_TYPE,
        "Connection": "keep-alive",
    }
    
    timeouts = timeout_override or (config.CONNECT_TIMEOUT, config.READ_TIMEOUT)
    
    logger.info(f"Consultando reporte: {ReportConfig.REPORT_NAME}")
    logger.info(f"Timeout: conexión={timeouts[0]}s, lectura={timeouts[1]}s")
    
    session = requests.Session()
    retry_strategy = Urllib3Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapterWithSocketKeepalive(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    for intento in range(1, reintentos + 1):
        try:
            if intento > 1:
                logger.warning(f"Reintentando (intento {intento}/{reintentos})...")
                time.sleep(config.RETRY_DELAY)
            
            logger.info(f"Enviando petición (intento {intento}/{reintentos})...")
            
            inicio = time.time()
            response = session.post(
                config.BASE_URL,
                data=ReportConfig.REPORT_NAME,
                headers=headers,
                verify=VERIFY_SSL,
                timeout=timeouts,
                stream=True
            )
            
            duracion = time.time() - inicio
            logger.info(f"Respuesta en {duracion:.2f} segundos")
            
            if response.status_code == 200:
                buffer = BytesIO()
                chunk_size = 10 * 1024 * 1024  # 10MB
                bytes_recibidos = 0
                progreso_intervalo = 50 * 1024 * 1024
                ultimo_log = 0
                
                try:
                    for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                        if chunk:
                            buffer.write(chunk)
                            bytes_recibidos += len(chunk)
                            if bytes_recibidos - ultimo_log >= progreso_intervalo:
                                logger.info(f"Descargados {bytes_recibidos / (1024*1024):.2f} MB...")
                                ultimo_log = bytes_recibidos
                except (requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ConnectionError,
                        urllib3.exceptions.IncompleteRead) as e:
                    logger.critical(f"Descarga interrumpida: {type(e).__name__}")
                    logger.critical(f"Bytes descargados: {bytes_recibidos}")
                    raise ReportError(f"Descarga interrumpida: {e}")
                
                contenido = buffer.getvalue()
                tamanio_mb = len(contenido) / (1024 * 1024)
                logger.info(f"Reporte obtenido ({tamanio_mb:.2f} MB)")
                return contenido.decode('utf-8', errors='replace')
            
            else:
                logger.error(f"Error HTTP: {response.status_code}")
                logger.error(f"Respuesta: {response.text[:500]}")
                raise ReportError(f"HTTP {response.status_code}")
        
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout (intento {intento}/{reintentos})")
            if intento == reintentos:
                raise ReportTimeoutError(f"Timeout después de {reintentos} intentos")
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión: {e}")
            if intento == reintentos:
                raise ReportError(f"Error de conexión: {e}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en petición: {e}")
            if intento == reintentos:
                raise ReportError(f"Error de petición: {e}")
    
    return None


def filtrar_cis_por_tipo_servicecodes(
    json_data: Dict[str, Any],
    config: Optional[UCMDBConfig] = None
) -> List[Dict[str, Any]]:
    """Filtra los CIs por tipo específico."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    cis = json_data.get("cis", [])
    
    if not isinstance(cis, list):
        logger.warning("'cis' no es una lista válida")
        return []
    
    nodos_filtrados = [
        obj for obj in cis
        if obj.get("type") == config.TARGET_NODE_TYPE
    ]
    
    logger.info(f"Filtrados {len(nodos_filtrados)} nodos de tipo '{config.TARGET_NODE_TYPE}'")
    return nodos_filtrados


def validar_nit_en_relaciones_invertidas(
    json_data: Dict[str, Any],
    config: Optional[UCMDBConfig] = None
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Valida la consistencia de NITs en relaciones."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    if not isinstance(json_data, dict):
        logger.error("json_data debe ser un diccionario")
        return [], []
    
    cis = json_data.get("cis", [])
    relaciones = json_data.get("relations", [])
    
    if not cis or not relaciones:
        logger.warning("No hay CIs o relaciones para procesar")
        return [], []
    
    nodos_por_id: Dict[str, Dict[str, Any]] = {
        obj.get("ucmdbId"): obj for obj in cis if obj.get("ucmdbId")
    }
    
    inconsistencias_normales: List[Dict[str, str]] = []
    inconsistencias_particulares: List[Dict[str, str]] = []
    nodos_faltantes = 0
    nits_faltantes = 0
    procesadas = 0
    
    for idx, rel in enumerate(relaciones, 1):
        if idx % max(len(relaciones) // 5, 1) == 0:
            porcentaje = (idx / len(relaciones)) * 100
            logger.info(f"[{porcentaje:.0f}%] {idx}/{len(relaciones)}")
        
        end1_id = rel.get("end1Id")
        end2_id = rel.get("end2Id")
        
        nodo_end1 = nodos_por_id.get(end1_id)
        nodo_end2 = nodos_por_id.get(end2_id)
        
        if not (nodo_end1 and nodo_end2):
            nodos_faltantes += 1
            continue
        
        props1 = nodo_end1.get("properties", {})
        props2 = nodo_end2.get("properties", {})
        
        nit_end1 = props1.get(config.NIT_FIELD_END1)
        nit_end2 = props2.get(config.NIT_FIELD_END2)
        
        if nit_end1 is None or nit_end2 is None:
            nits_faltantes += 1
            continue
        
        nit_end1_norm = nit_end1.strip()
        nit_end2_norm = nit_end2.strip()
        
        if nit_end1_norm != nit_end2_norm:
            inconsistencia = {
                "ucmdbId": rel.get("ucmdbId"),
                "nit_end1": nit_end1_norm,
                "nit_end2": nit_end2_norm,
                "end1Id": end1_id,
                "end2Id": end2_id,
                "display_label_end1": props1.get("display_label", "N/A"),
                "display_label_end2": props2.get("display_label", "N/A")
            }
            inconsistencias_normales.append(inconsistencia)
        
        procesadas += 1
    
    logger.info(f"Procesadas: {procesadas}, Inconsistencias: {len(inconsistencias_normales)}")
    
    return inconsistencias_normales, inconsistencias_particulares


def validar_relaciones_usage_de_servicecodes(
    json_data: Dict[str, Any],
    config: Optional[UCMDBConfig] = None
) -> List[Dict[str, Any]]:
    """Valida relaciones de tipo 'usage' vinculadas a servicecodes."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    logger.info("=" * 80)
    logger.info("PASO 5.1: VALIDAR RELACIONES USAGE DE SERVICECODES")
    logger.info("=" * 80)
    
    if not isinstance(json_data, dict):
        logger.error("json_data debe ser un diccionario")
        return []
    
    cis = json_data.get("cis", [])
    relaciones = json_data.get("relations", [])
    
    if not cis or not relaciones:
        logger.warning("No hay CIs o relaciones para procesar")
        return []
    
    cis_por_id: Dict[str, Dict[str, Any]] = {
        ci.get("ucmdbId"): ci for ci in cis if ci.get("ucmdbId")
    }
    servicecodes = [ci for ci in cis if ci.get("type") == "clr_onyxservicecodes"]
    
    logger.info(f"CIs indexados: {len(cis_por_id)}, Servicecodes: {len(servicecodes)}")
    
    relaciones_usage_por_end2: Dict[str, List[Dict[str, Any]]] = {}
    for rel in relaciones:
        rel_type = rel.get("type", "").lower()
        if rel_type == "usage":
            end2id = rel.get("end2Id")
            if end2id:
                relaciones_usage_por_end2.setdefault(end2id, []).append(rel)
    
    relaciones_a_eliminar: List[Dict[str, Any]] = []
    
    for servicecode in servicecodes:
        servicecode_id = servicecode.get("ucmdbId")
        servicecode_label = servicecode.get("properties", {}).get("display_label", "N/A")
        
        relaciones_usage = relaciones_usage_por_end2.get(servicecode_id, [])
        
        if not relaciones_usage:
            continue
        
        for rel_usage in relaciones_usage:
            end1id = rel_usage.get("end1Id")
            rel_id = rel_usage.get("ucmdbId")
            
            ci_end1 = cis_por_id.get(end1id)
            if not ci_end1:
                continue
            
            ci_type = ci_end1.get("type")
            if ci_type != "business_application":
                continue
            
            end1_label = ci_end1.get("properties", {}).get("display_label", "N/A")
            
            relaciones_a_eliminar.append({
                "ucmdbId": rel_id,
                "end1Id": end1id,
                "end2Id": servicecode_id,
                "type": "usage",
                "display_label_end1": end1_label,
                "display_label_end2": servicecode_label,
                "ci_type_end1": "business_application",
                "ci_type_end2": "clr_onyxservicecodes"
            })
    
    logger.info(f"Relaciones usage a eliminar: {len(relaciones_a_eliminar)}")
    return relaciones_a_eliminar