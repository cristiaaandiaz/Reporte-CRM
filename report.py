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
READ_TIMEOUT = 300     # Timeout para leer respuesta (5 minutos para data grande)

# Configuración de reintentos
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos entre reintentos


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

            response = requests.post(
                UCMDB_BASE_URL,
                data=REPORT_NAME,
                headers=headers,
                verify=False,
                timeout=timeouts,
                stream=False
            )

            duracion = time.time() - inicio
            logger.info(f"Respuesta recibida en {duracion:.2f} segundos")

            if response.status_code == 200:
                tamanio_mb = len(response.text) / (1024 * 1024)
                logger.info(f"Reporte obtenido exitosamente ({tamanio_mb:.2f} MB de datos)")
                return response.text
            else:
                mensaje = f"Error al consultar el reporte. Código HTTP: {response.status_code}"
                logger.error(mensaje)
                logger.debug(f"Detalle: {response.text[:500]}")

                if 400 <= response.status_code < 500:
                    raise ReportError(mensaje)

                if intento == reintentos:
                    raise ReportError(mensaje)

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


def contar_letras(s: str) -> int:
    return sum(1 for c in s if c.isalpha())


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

    progreso_cada = max(len(relaciones) // 10, 1)

    for idx, rel in enumerate(relaciones, 1):
        if idx % progreso_cada == 0:
            porcentaje = (idx / len(relaciones)) * 100
            logger.info(
                f"Progreso: {idx}/{len(relaciones)} relaciones "
                f"({porcentaje:.1f}%) - "
                f"Inconsistencias normales: {len(inconsistencias_normales)} - "
                f"Inconsistencias particulares: {len(inconsistencias_particulares)}"
            )

        rel_id = rel.get("ucmdbId")
        end1_id = rel.get("end1Id")
        end2_id = rel.get("end2Id")

        nodo_end1 = nodos_por_id.get(end1_id)
        nodo_end2 = nodos_por_id.get(end2_id)

        if not nodo_end1 or not nodo_end2:
            nodos_faltantes += 1
            logger.debug(
                f"Relación {rel_id}: nodos no encontrados "
                f"(end1: {end1_id}, end2: {end2_id})"
            )
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
            if contar_letras(nit_end1_norm) > 0 or contar_letras(nit_end2_norm) > 0:
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
