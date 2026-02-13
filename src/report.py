"""
Módulo de Generación y Procesamiento de Reportes.

Gestiona la consulta del reporte desde UCMDB y proporciona
funciones para filtrar y validar información sobre NITs.
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

from .config import UCMDBConfig, ReportConfig
from .logger_config import obtener_logger

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


# ==================== CONFIGURACIÓN LOCAL ====================
class HTTPAdapterWithSocketKeepalive(HTTPAdapter):
    """HTTPAdapter que configura socket keep-alive para conexiones largas."""
    
    def init_poolmanager(self, *args, **kwargs):
        """Inicializa el pool manager con opciones de keep-alive."""
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


# ==================== FUNCIÓN PRINCIPAL DE CONSULTA ====================

def consultar_reporte_ucmdb(
    token: str,
    config: Optional[UCMDBConfig] = None,
    timeout_override: Optional[tuple] = None,
    reintentos: int = None
) -> Optional[str]:
    """
    Consulta el reporte JSON desde UCMDB.
    
    Args:
        token: Token JWT de autenticación
        config: Configuración de UCMDB (usa global si no se proporciona)
        timeout_override: Tupla (connect_timeout, read_timeout) personalizada
        reintentos: Número de reintentos (usa config.MAX_RETRIES si no se proporciona)
    
    Returns:
        String con el contenido JSON del reporte o None si falla
        
    Raises:
        ReportTimeoutError: Si se agota el límite de tiempo
        ReportError: Si hay errores en la consulta
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    if reintentos is None:
        reintentos = config.MAX_RETRIES
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": config.CONTENT_TYPE,
        "Connection": "keep-alive",
        "Keep-Alive": "timeout=600, max=100"
    }

    timeouts = timeout_override or (config.CONNECT_TIMEOUT, config.READ_TIMEOUT)

    logger.info(f"Consultando reporte UCMDB: {ReportConfig.REPORT_NAME}")
    logger.info(f"Configuración de timeout: Conexión={timeouts[0]}s, Lectura={timeouts[1]}s")

    # Crear sesión FUERA del loop para reutilizarla en reintentos
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
                logger.warning(f"Reintentando consulta de reporte (intento {intento}/{reintentos})...")
                time.sleep(config.RETRY_DELAY)

            logger.info(f"Enviando petición al servidor UCMDB (intento {intento}/{reintentos})...")

            inicio = time.time()
            
            response = session.post(
                config.BASE_URL,
                data=ReportConfig.REPORT_NAME,
                headers=headers,
                verify=False,
                timeout=timeouts,
                stream=True
            )

            duracion = time.time() - inicio
            logger.info(f"Respuesta recibida en {duracion:.2f} segundos")

            if response.status_code == 200:
                # Descargar en chunks para archivos grandes
                buffer = BytesIO()
                chunk_size = 10 * 1024 * 1024  # 10MB chunks
                bytes_recibidos = 0
                progreso_intervalo = 50 * 1024 * 1024  # Log cada 50MB
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
                    error_type = type(e).__name__
                    logger.critical(f"❌ CRÍTICO: Descarga interrumpida por {error_type}")
                    logger.critical(f"   Detalle: {str(e)}")
                    logger.critical(f"   Bytes descargados: {bytes_recibidos}")
                    logger.critical(f"   Causa probable: El servidor UCMDB cortó la conexión después de ~{bytes_recibidos/(1024*1024):.0f} MB")
                    logger.critical(f"   ")
                    logger.critical(f"   ⚠️  SOLUCIÓN REQUERIDA:")
                    logger.critical(f"   1. El servidor UCMDB tiene límite de tiempo/tamaño de conexión")
                    logger.critical(f"   2. Contactar al equipo de UCMDB/Infraestructura para:")
                    logger.critical(f"      - Aumentar timeout de conexión HTTP en UCMDB")
                    logger.critical(f"      - Aumentar límite máximo de transferencia de datos")
                    logger.critical(f"      - Revisar si hay firewall/proxy intermedio limitando conexiones")
                    logger.critical(f"   3. Alternativa: Solicitar que el reporte se divida en partes")
                    
                    contenido = buffer.getvalue()
                    if contenido and bytes_recibidos > (100 * 1024 * 1024):
                        logger.warning(f"Intentando procesar datos parciales descargados...")
                        try:
                            contenido_str = contenido.decode('utf-8', errors='replace')
                            logger.info(f"Tamaño de datos truncados: {len(contenido_str)} caracteres")
                            
                            patrones = ['},', '],']
                            posiciones = [(contenido_str.rfind(p), p) for p in patrones]
                            posiciones_validas = [(pos, pat) for pos, pat in posiciones if pos > 0]
                            
                            if posiciones_validas:
                                mejor_posicion, mejor_patron = max(posiciones_validas, key=lambda x: x[0])
                                contenido_str = contenido_str[:mejor_posicion + len(mejor_patron)]
                                logger.info(f"Truncado en patrón '{mejor_patron}' en posición {mejor_posicion}")
                            else:
                                ultimo_close = contenido_str.rfind('}')
                                if ultimo_close > 0:
                                    contenido_str = contenido_str[:ultimo_close + 1]
                                    logger.info(f"Truncado en último }} en posición {ultimo_close}")
                            
                            contenido_str = contenido_str.rstrip(', ')
                            
                            open_brackets = contenido_str.count('[')
                            close_brackets = contenido_str.count(']')
                            open_braces = contenido_str.count('{')
                            close_braces = contenido_str.count('}')
                            
                            logger.info(f"Conteo: [ {open_brackets} vs ] {close_brackets}, {{ {open_braces} vs }} {close_braces}")
                            
                            if open_braces == 0 or open_brackets == 0:
                                logger.error("ERROR: JSON no contiene estructura mínima válida")
                                raise ValueError("JSON truncado sin estructura mínima")
                            
                            cierres_necesarios = (']' * (open_brackets - close_brackets)) + ('}' * (open_braces - close_braces))
                            if cierres_necesarios:
                                contenido_str += cierres_necesarios
                                logger.info(f"Agregados {len(cierres_necesarios)} caracteres de cierre")
                            
                            contenido = contenido_str.encode('utf-8')
                            logger.info("JSON truncado recuperado y cerrado correctamente")
                        except Exception as fix_error:
                            logger.error(f"Error al recuperar JSON truncado: {type(fix_error).__name__}: {fix_error}")
                            logger.warning("El JSON truncado no puede ser procesado de forma segura")
                    else:
                        logger.critical("ERROR: No se descargaron suficientes datos. Abortar ejecución.")
                        raise ReportError(f"Descarga interrumpida sin datos suficientes: {str(e)}")
                
                contenido = buffer.getvalue()
                tamanio_mb = len(contenido) / (1024 * 1024)
                logger.info(f"Reporte obtenido exitosamente ({tamanio_mb:.2f} MB de datos)")
                return contenido.decode('utf-8', errors='replace')
            else:
                response_text = response.text or ""
                mensaje = f"Error al consultar el reporte. Código HTTP: {response.status_code}"
                logger.error(mensaje)
                logger.error(f"Cuerpo de la respuesta: {response_text[:2000]}")

                if 400 <= response.status_code < 500:
                    logger.info("Intentando solicitud alternativa con JSON para diagnóstico...")
                    try:
                        alt_headers = headers.copy()
                        alt_headers["Content-Type"] = "application/json"
                        alt_payload = {"reportName": ReportConfig.REPORT_NAME}
                        alt_resp = requests.post(
                            config.BASE_URL,
                            json=alt_payload,
                            headers=alt_headers,
                            verify=False,
                            timeout=timeouts,
                        )
                        logger.error(f"Alternativa: status {alt_resp.status_code}")
                        logger.error(f"Alternativa cuerpo: {alt_resp.text[:2000]}")
                        if alt_resp.status_code == 200:
                            return alt_resp.text
                    except Exception as e:
                        logger.exception(f"Fallo intento alternativo: {e}")

                    raise ReportError(f"{mensaje} - {response_text}")

                if intento == reintentos:
                    raise ReportError(f"{mensaje} - {response_text}")

                logger.warning("Error del servidor, reintentando...")
                continue

        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout al conectar con UCMDB después de {timeouts[0]}s (conexión) / {timeouts[1]}s (lectura)")
            if intento == reintentos:
                mensaje = (
                    f"Timeout agotado después de {reintentos} intentos. "
                    f"El servidor UCMDB está respondiendo lentamente o la conexión es inestable. "
                    f"Timeout configurado: {timeouts[0]}s (conexión), {timeouts[1]}s (lectura). "
                    f"Considere: "
                    f"1) Aumentar CONNECT_TIMEOUT a 120s, "
                    f"2) Verificar conectividad con {config.BASE_URL}, "
                    f"3) Revisar si hay firewall bloqueando la conexión."
                )
                logger.error(mensaje)
                raise ReportTimeoutError(mensaje)
            logger.info(f"Reintentando en {config.RETRY_DELAY} segundos ({intento}/{reintentos})...")
            continue

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión con UCMDB: {str(e)}")
            if intento == reintentos:
                raise ReportError(f"Error de conexión: {str(e)}")
            logger.info(f"Reintentando en {config.RETRY_DELAY} segundos...")
            continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición: {str(e)}")
            if intento == reintentos:
                raise ReportError(f"Error de petición: {str(e)}")
            logger.info(f"Reintentando en {config.RETRY_DELAY} segundos...")
            continue

    return None


# ==================== FUNCIONES DE FILTRADO Y VALIDACIÓN ====================

def filtrar_cis_por_tipo_servicecodes(
    json_data: Dict[str, Any],
    config: Optional[UCMDBConfig] = None
) -> List[Dict[str, Any]]:
    """
    Filtra los CIs (Configuration Items) por tipo específico.
    
    Args:
        json_data: Datos JSON del reporte
        config: Configuración de UCMDB (usa global si no se proporciona)
    
    Returns:
        Lista de CIs filtrados
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    cis = json_data.get("cis", [])

    if not isinstance(cis, list):
        logger.warning("El contenido de 'cis' no es una lista válida")
        return []

    nodos_filtrados = [
        obj for obj in cis
        if obj.get("type") == config.TARGET_NODE_TYPE
    ]

    logger.info(
        f"Filtrados {len(nodos_filtrados)} nodos de tipo '{config.TARGET_NODE_TYPE}' "
        f"de un total de {len(cis)} nodos"
    )
    return nodos_filtrados


def contar_letras(s: str) -> bool:
    """
    Verifica si hay al menos una letra en la cadena.
    
    Args:
        s: String a validar
    
    Returns:
        True si hay al menos una letra
    """
    return any(c.isalpha() for c in s)


def validar_nit_en_relaciones_invertidas(
    json_data: Dict[str, Any],
    config: Optional[UCMDBConfig] = None
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Valida la consistencia de NITs en relaciones entre sistemas.
    
    Args:
        json_data: Datos JSON del reporte
        config: Configuración de UCMDB (usa global si no se proporciona)
    
    Returns:
        Tupla con (inconsistencias_normales, inconsistencias_particulares)
    """
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

    # Crear índices eficientes
    nodos_por_id: Dict[str, Dict[str, Any]] = {}
    for obj in cis:
        ucmdb_id = obj.get("ucmdbId")
        if ucmdb_id:
            nodos_por_id[ucmdb_id] = obj
            if "_properties_cache" not in obj:
                obj["_properties_cache"] = obj.get("properties", {})

    inconsistencias_normales: List[Dict[str, str]] = []
    inconsistencias_particulares: List[Dict[str, str]] = []
    nodos_faltantes = 0
    nits_faltantes = 0
    procesadas = 0

    progreso_cada = max(len(relaciones) // 5, 1)

    for idx, rel in enumerate(relaciones, 1):
        if idx % progreso_cada == 0:
            porcentaje = (idx / len(relaciones)) * 100
            logger.info(
                f"[{porcentaje:.0f}%] {idx}/{len(relaciones)} | "
                f"Normales: {len(inconsistencias_normales)}, Particulares: {len(inconsistencias_particulares)}"
            )

        rel_id = rel.get("ucmdbId")
        end1_id = rel.get("end1Id")
        end2_id = rel.get("end2Id")

        nodo_end1 = nodos_por_id.get(end1_id)
        nodo_end2 = nodos_por_id.get(end2_id)

        if not (nodo_end1 and nodo_end2):
            nodos_faltantes += 1
            continue

        props1 = nodo_end1.get("_properties_cache", nodo_end1.get("properties", {}))
        props2 = nodo_end2.get("_properties_cache", nodo_end2.get("properties", {}))
        
        nit_end1 = props1.get(config.NIT_FIELD_END1)
        nit_end2 = props2.get(config.NIT_FIELD_END2)

        if nit_end1 is None or nit_end2 is None:
            nits_faltantes += 1
            continue

        nit_end1_norm = nit_end1.strip()
        nit_end2_norm = nit_end2.strip()

        if nit_end1_norm != nit_end2_norm:
            display_label_end1 = props1.get("display_label", "N/A")
            display_label_end2 = props2.get("display_label", "N/A")
            
            inconsistencia = {
                "ucmdbId": rel_id,
                "nit_end1": nit_end1_norm,
                "nit_end2": nit_end2_norm,
                "end1Id": end1_id,
                "end2Id": end2_id,
                "display_label_end1": display_label_end1,
                "display_label_end2": display_label_end2
            }
            
            if contar_letras(nit_end1_norm) or contar_letras(nit_end2_norm):
                inconsistencias_particulares.append(inconsistencia)
            else:
                inconsistencias_normales.append(inconsistencia)

        procesadas += 1

    logger.info("=" * 60)
    logger.info("Resumen de validación de NITs:")
    logger.info(f"  Total de relaciones procesadas: {procesadas}")
    logger.info(f"  Inconsistencias normales encontradas: {len(inconsistencias_normales)}")
    logger.info(f"  Inconsistencias particulares encontradas: {len(inconsistencias_particulares)}")
    logger.info(f"  Nodos faltantes: {nodos_faltantes}")
    logger.info(f"  NITs faltantes: {nits_faltantes}")
    logger.info("=" * 60)

    return inconsistencias_normales, inconsistencias_particulares
