import os
import logging
import time
from typing import Optional, Dict, List, Any, Tuple

import requests
import urllib3
from dotenv import load_dotenv

# Configuración de logging
logger = logging.getLogger(__name__)

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cargar variables de entorno
load_dotenv()

# Constantes de configuración
UCMDB_BASE_URL = os.getenv("UCMDB_URL", "https://10.110.0.62:8443/rest-api/topology")
CONTENT_TYPE = "text/plain"
REPORT_NAME = "Reporte_Clientes_Onyx-uCMDB"
TARGET_NODE_TYPE = "clr_onyxservicecodes"
NIT_FIELD_END1 = "clr_onyxdb_company_nit"
NIT_FIELD_END2 = "clr_onyxdb_companynit"

# Configuración de timeouts (en segundos)
CONNECT_TIMEOUT = 30  # Timeout para establecer conexión
READ_TIMEOUT = 600    # Timeout para leer respuesta (10 minutos para data grande de 235MB)

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre reintentos

# Pool de conexiones para reutilizar conexiones
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry as Urllib3Retry


class ReportTimeoutError(Exception):
    pass


class ReportError(Exception):
    pass


def consultar_reporte_ucmdb(
    token: str,
    timeout_override: Optional[tuple[int, int]] = None,
    reintentos: int = MAX_RETRIES
) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": CONTENT_TYPE
    }

    timeouts = timeout_override or (CONNECT_TIMEOUT, READ_TIMEOUT)

    logger.info(f"Consultando reporte UCMDB: {REPORT_NAME}")
    logger.info(f"Configuración de timeout: Conexión={timeouts[0]}s, Lectura={timeouts[1]}s")

    for intento in range(1, reintentos + 1):
        try:
            if intento > 1:
                logger.warning(f"Reintentando consulta de reporte (intento {intento}/{reintentos})...")
                time.sleep(RETRY_DELAY)

            logger.info(f"Enviando petición al servidor UCMDB (intento {intento}/{reintentos})...")

            inicio = time.time()

            # Crear sesión con configuración especial para archivos grandes
            session = requests.Session()
            
            # Configurar reintentos con backoff
            retry_strategy = Urllib3Retry(
                total=1,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.post(
                UCMDB_BASE_URL,
                data=REPORT_NAME,
                headers=headers,
                verify=False,
                timeout=timeouts,
                stream=True
            )

            duracion = time.time() - inicio
            logger.info(f"Respuesta recibida en {duracion:.2f} segundos")

            if response.status_code == 200:
                # Descargar en chunks para archivos grandes, con mejor manejo de errores
                contenido = b""
                chunk_size = 32768  # 32KB chunks
                bytes_recibidos = 0
                try:
                    for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                        if chunk:
                            contenido += chunk
                            bytes_recibidos += len(chunk)
                            # Log cada 50MB
                            if bytes_recibidos % (50 * 1024 * 1024) == 0:
                                logger.info(f"Descargados {bytes_recibidos / (1024*1024):.2f} MB...")
                except (requests.exceptions.ChunkedEncodingError, 
                        requests.exceptions.ConnectionError) as e:
                    logger.warning(f"Error durante descarga: {str(e)}")
                    if contenido:
                        logger.warning("Se obtuvieron datos parciales, intentando procesarlos...")
                        # Intentar recuperar del error truncando al último JSON válido
                        try:
                            contenido_str = contenido.decode('utf-8', errors='replace')
                            logger.info(f"Tamaño de datos truncados: {len(contenido_str)} caracteres")
                            
                            # Estrategia 1: Buscar el último } que cierre la estructura principal
                            # La estructura es: { "cis": [...], "relations": [...] }
                            # Intentamos encontrar el cierre de "relations": []
                            
                            # Primero, buscar la última ocurrencia de ]}} (cierre de relations y objeto principal)
                            ultimo_array_close = contenido_str.rfind("]}}")
                            if ultimo_array_close > 0:
                                logger.info("Encontrado cierre ]}} - usando eso como límite")
                                contenido_str = contenido_str[:ultimo_array_close+3]
                            else:
                                # Estrategia 2: Si no funciona, buscar el último array válido ]
                                logger.info("No encontrado }}] - buscando último array válido...")
                                
                                # Encontrar la última línea que tenga una estructura válida
                                lineas = contenido_str.split('\n')
                                for i in range(len(lineas)-1, -1, -1):
                                    linea = lineas[i].strip()
                                    # Si la línea termina con }, ], o },] es probablemente válida
                                    if linea.endswith('}') or linea.endswith(']') or linea.endswith('},') or linea.endswith('],'):
                                        logger.info(f"Línea válida encontrada en posición {i}: {linea[:80]}...")
                                        contenido_str = '\n'.join(lineas[:i+1])
                                        
                                        # Ahora necesitamos cerrar la estructura abierta
                                        # Contar los [ y ] para saber cuántos cerrar
                                        open_brackets = contenido_str.count('[')
                                        close_brackets = contenido_str.count(']')
                                        open_braces = contenido_str.count('{')
                                        close_braces = contenido_str.count('}')
                                        
                                        logger.info(f"Brackets: {open_brackets} open vs {close_brackets} close")
                                        logger.info(f"Braces: {open_braces} open vs {close_braces} close")
                                        
                                        # Agregar los cierres necesarios
                                        if open_brackets > close_brackets:
                                            contenido_str += '\n' + ']' * (open_brackets - close_brackets)
                                        if open_braces > close_braces:
                                            contenido_str += '\n' + '}' * (open_braces - close_braces)
                                        
                                        break
                            
                            contenido = contenido_str.encode('utf-8')
                            logger.info("JSON truncado recuperado")
                        except Exception as fix_error:
                            logger.warning(f"No se pudo recuperar JSON: {fix_error}")
                    else:
                        raise
                
                tamanio_mb = len(contenido) / (1024 * 1024)
                logger.info(f"Reporte obtenido exitosamente ({tamanio_mb:.2f} MB de datos)")
                return contenido.decode('utf-8', errors='replace')
            else:
                # Guardar detalle del cuerpo para facilitar depuración
                response_text = response.text or ""
                mensaje = f"Error al consultar el reporte. Código HTTP: {response.status_code}"
                logger.error(mensaje)
                logger.error(f"Cuerpo de la respuesta: {response_text[:2000]}")

                # Si es 4xx intentamos un intento alternativo con JSON (diagnóstico)
                if 400 <= response.status_code < 500:
                    logger.info("Intentando solicitud alternativa con JSON para diagnóstico...")
                    try:
                        alt_headers = headers.copy()
                        alt_headers["Content-Type"] = "application/json"
                        alt_payload = {"reportName": REPORT_NAME}
                        alt_resp = requests.post(
                            UCMDB_BASE_URL,
                            json=alt_payload,
                            headers=alt_headers,
                            verify=False,
                            timeout=timeouts,
                        )
                        logger.error(f"Alternativa: status {alt_resp.status_code}")
                        logger.error(f"Alternativa cuerpo: {alt_resp.text[:2000]}")
                        # Si la alternativa funciona, devolver su contenido
                        if alt_resp.status_code == 200:
                            return alt_resp.text
                    except Exception as e:
                        logger.exception(f"Fallo intento alternativo: {e}")

                    # No sirvió la alternativa, propagar el mensaje original
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
                    f"El reporte puede ser demasiado grande para el timeout "
                    f"configurado ({timeouts[1]}s). "
                    f"Considere aumentar READ_TIMEOUT o usar timeout_override."
                )
                logger.error(mensaje)
                raise ReportTimeoutError(mensaje)
            logger.info(f"Reintentando en {RETRY_DELAY} segundos ({intento}/{reintentos})...")
            continue

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión con UCMDB: {str(e)}")
            if intento == reintentos:
                raise ReportError(f"Error de conexión: {str(e)}")
            logger.info(f"Reintentando en {RETRY_DELAY} segundos...")
            continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición: {str(e)}")
            if intento == reintentos:
                raise ReportError(f"Error de petición: {str(e)}")
            logger.info(f"Reintentando en {RETRY_DELAY} segundos...")
            continue

    return None


def filtrar_cis_por_tipo_servicecodes(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    cis = json_data.get("cis", [])

    if not isinstance(cis, list):
        logger.warning("El contenido de 'cis' no es una lista válida")
        return []

    nodos_filtrados = [
        obj for obj in cis
        if obj.get("type") == TARGET_NODE_TYPE
    ]

    logger.info(
        f"Filtrados {len(nodos_filtrados)} nodos de tipo '{TARGET_NODE_TYPE}' "
        f"de un total de {len(cis)} nodos"
    )
    return nodos_filtrados


def extraer_datos_relevantes_servicecodes(cis_filtrados: List[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    resultado = []

    for obj in cis_filtrados:
        properties = obj.get("properties", {})
        resultado.append({
            "type": obj.get("type"),
            "display_label": properties.get("display_label"),
            "company_nit": properties.get(NIT_FIELD_END1)
        })

    logger.info(f"Extraídos {len(resultado)} registros de servicecodes")
    return resultado


def contar_letras(s: str) -> bool:
    """Retorna True si hay al menos una letra (optimizado para validación)."""
    return any(c.isalpha() for c in s)


def validar_nit_en_relaciones_invertidas(
    json_data: Dict[str, Any]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    if not isinstance(json_data, dict):
        logger.error("json_data debe ser un diccionario")
        return [], []

    cis = json_data.get("cis", [])
    relaciones = json_data.get("relations", [])

    if not cis or not relaciones:
        logger.warning("No hay CIs o relaciones para procesar")
        return [], []

    nodos_por_id: Dict[str, Dict[str, Any]] = {
        obj.get("ucmdbId"): obj
        for obj in cis
        if obj.get("ucmdbId")
    }

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

        if not nodo_end1 or not nodo_end2:
            nodos_faltantes += 1
            logger.debug(f"Relación {rel_id}: nodo faltante (end1={end1_id}, end2={end2_id})")
            continue

        nit_end1 = nodo_end1.get("properties", {}).get(NIT_FIELD_END1)
        nit_end2 = nodo_end2.get("properties", {}).get(NIT_FIELD_END2)

        if nit_end1 is None or nit_end2 is None:
            nits_faltantes += 1
            logger.debug(f"Relación {rel_id}: NITs faltantes")
            continue

        nit_end1_norm = nit_end1.strip()
        nit_end2_norm = nit_end2.strip()

        if nit_end1_norm != nit_end2_norm:
            if contar_letras(nit_end1_norm) or contar_letras(nit_end2_norm):
                inconsistencias_particulares.append({
                    "ucmdbId": rel_id,
                    "nit_end1": nit_end1_norm,
                    "nit_end2": nit_end2_norm,
                })
            else:
                inconsistencias_normales.append({
                    "ucmdbId": rel_id,
                    "nit_end1": nit_end1_norm,
                    "nit_end2": nit_end2_norm,
                })

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


def eliminar_relacion_ucmdb(token: str, relacion_id: str) -> bool:
    """
    Elimina una relación en UCMDB por su ucmdbId usando DELETE.

    Args:
        token (str): Token JWT de autenticación.
        relacion_id (str): ucmdbId de la relación a eliminar.

    Returns:
        bool: True si la eliminación fue exitosa (200), False en caso de error.
    """
    url = f"https://ucmdbapp.triara.co:8443/rest-api/dataModel/relation/{relacion_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    # Implementar reintentos para mayor robustez en la eliminación
    for intento in range(1, MAX_RETRIES + 1):
        try:
            response = requests.delete(
                url,
                headers=headers,
                verify=False,
                timeout=30
            )
            logger.info(f"DELETE {url} - Status: {response.status_code} (intento {intento}/{MAX_RETRIES})")

            if response.status_code == 200:
                logger.info(f"Relación {relacion_id} eliminada correctamente")
                return True

            # 4xx => fallo permanente, no reintentar
            if 400 <= response.status_code < 500:
                logger.warning(
                    f"[UCMDB-DELETE] {response.status_code} - Relación {relacion_id}: {response.text[:150]}"
                )
                return False

            # 5xx => reintentar hasta agotar
            logger.warning(
                f"Respuesta {response.status_code} del servidor al eliminar {relacion_id}. Reintentando..."
            )

        except requests.exceptions.Timeout:
            logger.error(f"[UCMDB-DELETE] TIMEOUT - Relación {relacion_id} ({intento}/{MAX_RETRIES})")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[UCMDB-DELETE] CONEXIÓN ERROR - Relación {relacion_id}: {str(e)[:80]}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[UCMDB-DELETE] ERROR - Relación {relacion_id}: {str(e)[:80]}")

        # Esperar antes de reintentar (backoff simple)
        if intento < MAX_RETRIES:
            time.sleep(RETRY_DELAY * intento)

    logger.error(f"[UCMDB-DELETE] FALLO FINAL - Relación {relacion_id} ({MAX_RETRIES} intentos agotados)")
    return False
