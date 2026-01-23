"""
Script de validación y eliminación de inconsistencias de NITs en UCMDB e ITSM.

Este script:
1. Autentica contra UCMDB
2. Obtiene un reporte JSON de relaciones
3. Valida la consistencia de NITs
4. Simula o ejecuta eliminaciones en UCMDB e ITSM

Configuración controlada por flags MODO_EJECUCION, GENERAR_RESUMEN y CREAR_CARPETA_EJECUCION.
"""

import json
import os
import sys
import logging
import time
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import requests
import urllib3
from dotenv import load_dotenv

from auth import obtener_token_ucmdb
from report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    extraer_datos_relevantes_servicecodes,
    validar_nit_en_relaciones_invertidas,
    eliminar_relacion_ucmdb,
)

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cargar variables de entorno
load_dotenv()

# ==================== CONFIGURACIÓN DE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ucmdb_validation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURACIÓN GENERAL ====================
REPORTS_BASE_DIR = "reports"

# Control manual - Modo de ejecución para AMBAS APIs (UCMDB + ITSM)
# "simulacion" => DRY-RUN (recomendado primero)
# "ejecucion" => Eliminaciones REALES en producción
MODO_EJECUCION = "simulacion"

# Control manual - Generación de reportes
GENERAR_RESUMEN = True
CREAR_CARPETA_EJECUCION = True

# ==================== CONFIGURACIÓN UCMDB ====================
UCMDB_BASE_URL = "https://ucmdbapp.triara.co:8443/rest-api"
UCMDB_DELETE_ENDPOINT = f"{UCMDB_BASE_URL}/dataModel/relation"
UCMDB_TIMEOUT = 30

# ==================== CONFIGURACIÓN ITSM ====================
# CRÍTICO: Credenciales DEBEN estar en .env - sin defaults hardcodeados
ITSM_BASE_URL = os.getenv("ITSM_URL")
ITSM_USERNAME = os.getenv("ITSM_USERNAME")
ITSM_PASSWORD = os.getenv("ITSM_PASSWORD")

if not all([ITSM_BASE_URL, ITSM_USERNAME, ITSM_PASSWORD]):
    logger.error("ERROR CRÍTICO: Credenciales ITSM faltantes en .env")
    logger.error("  Requeridas: ITSM_URL, ITSM_USERNAME, ITSM_PASSWORD")
    sys.exit(1)

ITSM_TIMEOUT = 30
ITSM_MAX_RETRIES = 3
ITSM_RETRY_DELAY = 2

# ==================== CÓDIGOS DE SALIDA ====================
EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 1
EXIT_REPORT_ERROR = 2
EXIT_JSON_ERROR = 3

# ==================== FUNCIONES UTILIDAD ====================

def crear_directorio_ejecucion() -> Path:
    """
    Crea directorio de ejecución con timestamp.
    
    Returns:
        Path: Ruta del directorio creado o Path a 'disabled' si está deshabilitado.
    """
    if not CREAR_CARPETA_EJECUCION:
        logger.info("Creación de carpeta de ejecución deshabilitada")
        return Path(REPORTS_BASE_DIR) / "disabled"
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = Path(REPORTS_BASE_DIR) / f"ejecucion_{timestamp}"
    carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
    return carpeta_ejecucion


def _es_carpeta_deshabilitada(carpeta: Path) -> bool:
    """Verifica si la carpeta está deshabilitada."""
    return carpeta.name == "disabled"


# ==================== FUNCIONES DE GUARDADO ====================

def guardar_reporte_json(json_data: Dict[str, Any], carpeta: Path) -> Optional[Path]:
    """Guarda el JSON completo del reporte."""
    if _es_carpeta_deshabilitada(carpeta):
        logger.info("Guardado de reporte JSON deshabilitado")
        return None
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archivo_reporte = carpeta / f"reporte_{timestamp}.json"
    
    try:
        with open(archivo_reporte, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Reporte guardado: {archivo_reporte}")
        return archivo_reporte
    except IOError as e:
        logger.error(f"Error al guardar reporte JSON: {e}")
        return None


def guardar_inconsistencias_detalle(
    inconsistencias: List[Dict[str, Any]],
    carpeta: Path,
    nombre_archivo: str
) -> Optional[Path]:
    """Guarda detalle de inconsistencias encontradas."""
    if not inconsistencias:
        logger.info(f"Sin inconsistencias para {nombre_archivo}")
        return None

    if _es_carpeta_deshabilitada(carpeta):
        logger.info(f"Guardado de {nombre_archivo} deshabilitado")
        return None

    archivo = carpeta / nombre_archivo

    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("Reporte detallado de Inconsistencias de NITs\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write(f"Total: {len(inconsistencias)}\n")
            f.write("=" * 80 + "\n\n")

            for i, item in enumerate(inconsistencias, start=1):
                f.write(f"{i}. ucmdbId: {item['ucmdbId']}\n")
                f.write(f"   NIT end1: {item.get('nit_end1', 'N/A')} ({item.get('end1_ucmdbid', 'N/A')})\n")
                f.write(f"   NIT end2: {item.get('nit_end2', 'N/A')} ({item.get('end2_ucmdbid', 'N/A')})\n")
                f.write(f"   relacion_fo: {'true' if item.get('relacion_fo') else 'false'}\n")
                f.write(f"   ucmdbid_fo: {item.get('ucmdbid_fo', 'N/A')}\n\n")

        logger.info(f"Inconsistencias guardadas: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando {nombre_archivo}: {e}")
        return None


# ==================== FUNCIONES ITSM - ELIMINACIONES ====================

def _crear_headers_itsm() -> Dict[str, str]:
    """
    Crea headers de autenticación Basic Auth para ITSM.
    
    Returns:
        Dict con headers incluyendo Authorization y Content-Type.
    """
    credenciales = f"{ITSM_USERNAME}:{ITSM_PASSWORD}"
    credenciales_encoded = base64.b64encode(credenciales.encode()).decode()
    
    return {
        "Authorization": f"Basic {credenciales_encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def ejecutar_update_itsm(url: str) -> Tuple[bool, str]:
    """
    Ejecuta PUT en ITSM con reintentos automáticos para marcar relaciones como "Removed".
    
    Args:
        url (str): URL completa del endpoint PUT en ITSM
        
    Returns:
        Tuple[bool, str]: (Éxito, Mensaje descriptivo)
    """
    # Validación crítica: URL no debe estar vacía
    if not url or not url.strip():
        return False, "URL vacía"
    
    headers = _crear_headers_itsm()
    payload = {
        "cirelationship1to1": {
            "status": "Removed"
        }
    }
    
    for intento in range(1, ITSM_MAX_RETRIES + 1):
        try:
            logger.debug(f"   PUT ITSM intento {intento}/{ITSM_MAX_RETRIES}")
            logger.debug(f"   URL: {url}")
            logger.debug(f"   Payload: {json.dumps(payload)}")
            
            response = requests.put(
                url,
                json=payload,
                headers=headers,
                verify=False,
                timeout=ITSM_TIMEOUT
            )
            
            logger.debug(f"   HTTP {response.status_code}")
            
            # Éxito: 200, 201, 202, 204
            if response.status_code in [200, 201, 202, 204]:
                return True, f"HTTP {response.status_code} OK"
            
            # Error permanente (4xx) - no reintentar
            if 400 <= response.status_code < 500:
                error_msg = response.text[:200] if response.text else "Sin detalles"
                logger.debug(f"   Respuesta 4xx: {error_msg}")
                return False, f"HTTP {response.status_code} - Error permanente: {error_msg[:80]}"
            
            # Error temporal (5xx) - reintentar
            if 500 <= response.status_code < 600:
                if intento < ITSM_MAX_RETRIES:
                    logger.warning(f"   HTTP {response.status_code} - Reintentando...")
                    time.sleep(ITSM_RETRY_DELAY)
                    continue
                return False, f"HTTP {response.status_code} - Servidor error (agotados reintentos)"
        
        except requests.exceptions.Timeout as e:
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   TIMEOUT - Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"TIMEOUT - Agotados {ITSM_MAX_RETRIES} intentos"
        
        except requests.exceptions.ConnectionError as e:
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   Error conexión - Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"Error conexión: {str(e)[:80]}"
        
        except Exception as e:
            logger.error(f"   Error inesperado: {str(e)}")
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"Error: {str(e)[:80]}"
    
    return False, "Error desconocido"


def eliminar_en_itsm(
    inconsistencias_normales_con_fo: List[Dict[str, Any]],
    carpeta: Path
) -> None:
    """
    Procesa actualizaciones en ITSM SOLO para relaciones con relacion_fo: true.
    Endpoint: PUT /SM/9/rest/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}
    Body: {"cirelationship1to1": {"status": "Removed"}}
    
    GARANTÍA: Solo procesa si ucmdbid_fo es válido (no "N/A")
    VALIDACIONES: URL construida, IDs no vacíos, payload correcto
    
    Args:
        inconsistencias_normales_con_fo: Lista de relaciones con fo:true
        carpeta: Ruta para guardar resumen
    """
    logger.info("=" * 80)
    logger.info("PASO 6B: ACTUALIZAR EN ITSM (Sistema de Gestión de Servicios TI)")
    logger.info("=" * 80)
    
    # VALIDACIÓN CRÍTICA: ITSM_BASE_URL configurado
    if not ITSM_BASE_URL:
        logger.error("ERROR CRÍTICO: ITSM_BASE_URL no está configurada en .env")
        logger.error("  Requerida: ITSM_BASE_URL (ej: https://servidor:puerto/SM/9/rest)")
        return
    
    logger.info(f"ITSM_BASE_URL configurada: {ITSM_BASE_URL}")
    
    if MODO_EJECUCION == "ejecucion":
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
        return
    
    resumen = []
    exitosas = 0
    fallidas = 0
    
    for idx, item in enumerate(relaciones_validas, 1):
        ucmdbid = item.get("ucmdbId", "").strip()
        ucmdbid_fo = item.get("ucmdbid_fo", "").strip()
        
        # VALIDACIONES DE DATOS
        if not ucmdbid or not ucmdbid_fo:
            logger.warning(f"[{idx}/{total}] SALTADO: IDs vacíos (ucmdbid={ucmdbid}, ucmdbid_fo={ucmdbid_fo})")
            continue
        
        # Construcción de URL según spec: /SM/9/rest/cirelationship1to1s/{UcmdbID_fo}/{UcmdbID}
        url = f"{ITSM_BASE_URL}/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}"
        
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
            "modo": "EJECUCION" if MODO_EJECUCION == "ejecucion" else "SIMULACION",
            "estado": "PENDIENTE",
            "detalles": ""
        }
        
        if MODO_EJECUCION == "ejecucion":
            exito, mensaje = ejecutar_update_itsm(url)
            if exito:
                resultado["estado"] = "EXITOSA"
                resultado["detalles"] = mensaje
                exitosas += 1
                logger.info(f"  ✓ {mensaje}")
            else:
                resultado["estado"] = "FALLIDA"
                resultado["detalles"] = mensaje
                fallidas += 1
                logger.error(f"  ✗ {mensaje}")
        else:
            # SIMULACIÓN
            resultado["estado"] = "SIMULADA"
            resultado["detalles"] = "Listo para ejecutarse"
            logger.info(f"  [SIMULACIÓN] URL: {url}")
            logger.info(f"  [SIMULACIÓN] Body: {json.dumps(resultado['body'])}")
        
        resumen.append(resultado)
    
    logger.info("-" * 80)
    logger.info("Resumen ITSM:")
    logger.info(f"  Total procesadas: {total}")
    logger.info(f"  Exitosas: {exitosas}")
    logger.info(f"  Fallidas: {fallidas}")
    if MODO_EJECUCION != "ejecucion":
        logger.info(f"  Simuladas: {total}")
    
    guardar_resumen_itsm(resumen, carpeta)


def guardar_resumen_itsm(
    resumen: List[Dict[str, Any]],
    carpeta: Path
) -> Optional[Path]:
    """Guarda resumen de operaciones ITSM."""
    if not GENERAR_RESUMEN:
        logger.info("Generación de resumen ITSM deshabilitada")
        return None
    
    if _es_carpeta_deshabilitada(carpeta):
        logger.info("Guardado de resumen ITSM deshabilitado")
        return None
    
    archivo = carpeta / "resumen_itsm.txt"
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("RESUMEN DE ACTUALIZACIONES EN ITSM\n")
            f.write("=" * 80 + "\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write(f"Modo: {MODO_EJECUCION.upper()}\n")
            f.write(f"Método: PUT (Marcar como 'Removed')\n")
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"{item['numero']}. ucmdbId: {item['ucmdbId']}\n")
                f.write(f"   ucmdbid_fo: {item['ucmdbid_fo']}\n")
                f.write(f"   URL: {item['url']}\n")
                f.write(f"   Método: {item.get('metodo', 'N/A')}\n")
                f.write(f"   Body: {json.dumps(item.get('body', {}))}\n")
                f.write(f"   Estado: {item['estado']}\n")
                f.write(f"   Detalles: {item['detalles']}\n\n")
        
        logger.info(f"Resumen ITSM guardado: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando resumen ITSM: {e}")
        return None


# ==================== FUNCIONES UCMDB - ELIMINACIONES ====================

def ejecutar_delete_ucmdb(url: str, token: str) -> Tuple[bool, str]:
    """
    Ejecuta DELETE en UCMDB con reintentos automáticos.
    
    Args:
        url (str): URL completa del endpoint DELETE en UCMDB
        token (str): Token JWT para autenticación
        
    Returns:
        Tuple[bool, str]: (Éxito, Mensaje descriptivo)
    """
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    for intento in range(1, ITSM_MAX_RETRIES + 1):
        try:
            logger.debug(f"  DELETE intento {intento}/{ITSM_MAX_RETRIES}...")
            response = requests.delete(url, headers=headers, verify=False, timeout=UCMDB_TIMEOUT)
            
            logger.debug(f"   HTTP {response.status_code}")
            
            # Éxito: 200, 202, 204
            if response.status_code in [200, 202, 204]:
                return True, f"HTTP {response.status_code} OK"
            
            # Error permanente (4xx) - no reintentar
            if 400 <= response.status_code < 500:
                error_msg = response.text[:100] if response.text else "Sin detalles"
                return False, f"HTTP {response.status_code} - Error permanente"
            
            # Error temporal (5xx) - reintentar
            if 500 <= response.status_code < 600:
                if intento < ITSM_MAX_RETRIES:
                    logger.warning(f"   HTTP {response.status_code} - Reintentando...")
                    time.sleep(ITSM_RETRY_DELAY)
                    continue
                return False, f"HTTP {response.status_code} - Servidor error (agotados reintentos)"
        
        except requests.exceptions.Timeout:
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   TIMEOUT - Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"TIMEOUT - Agotados {ITSM_MAX_RETRIES} intentos"
        
        except requests.exceptions.ConnectionError as e:
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   Error conexión - Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"Error conexión: {str(e)[:80]}"
        
        except Exception as e:
            if intento < ITSM_MAX_RETRIES:
                logger.warning(f"   Error inesperado - Reintentando ({intento}/{ITSM_MAX_RETRIES})...")
                time.sleep(ITSM_RETRY_DELAY)
                continue
            return False, f"Error: {str(e)[:80]}"
    
    return False, "Error desconocido"


def eliminar_en_ucmdb(
    token: str,
    inconsistencias: List[Dict[str, Any]],
    carpeta: Path
) -> None:
    """
    Procesa eliminaciones en UCMDB para TODAS las relaciones normales.
    Endpoint: DELETE /dataModel/relation/{ucmdbid}
    
    Args:
        token: Token JWT de autenticación UCMDB
        inconsistencias: Lista de ALL relaciones normales (con o sin fo)
        carpeta: Ruta para guardar resumen
    """
    logger.info("=" * 80)
    logger.info("PASO 6A: ELIMINAR EN UCMDB")
    logger.info("=" * 80)
    
    if MODO_EJECUCION == "ejecucion":
        logger.warning("[EJECUCIÓN REAL] Se ejecutarán DELETE en UCMDB con reintentos")
    else:
        logger.info("[SIMULACIÓN] Se mostrarán URLs sin ejecutar")
    
    total = len(inconsistencias)
    logger.info(f"Total de relaciones a procesar: {total}")
    logger.info("-" * 80)
    
    if not inconsistencias:
        logger.info("No hay inconsistencias para procesar")
        return
    
    exitosas = 0
    fallidas = 0
    
    for idx, item in enumerate(inconsistencias, 1):
        ucmdbid = item.get("ucmdbId")
        url = f"{UCMDB_DELETE_ENDPOINT}/{ucmdbid}"
        
        logger.info(f"[{idx}/{total}] Procesando: {ucmdbid}")
        logger.debug(f"  URL: {url}")
        
        if MODO_EJECUCION == "ejecucion":
            # EJECUCIÓN REAL con reintentos
            exito, mensaje = ejecutar_delete_ucmdb(url, token)
            if exito:
                exitosas += 1
                logger.info(f"  ✓ {mensaje}")
            else:
                fallidas += 1
                logger.error(f"  ✗ {mensaje}")
        else:
            logger.info(f"  [SIMULACIÓN] Se eliminaría con DELETE {url}")
    
    logger.info("-" * 80)
    logger.info("Resumen UCMDB:")
    logger.info(f"  Total procesadas: {total}")
    
    if MODO_EJECUCION == "ejecucion":
        logger.info(f"  Exitosas: {exitosas}")
        logger.info(f"  Fallidas: {fallidas}")
    else:
        logger.info(f"  Simuladas: {total}")


# ==================== FUNCIONES DE PROCESAMIENTO ====================

def procesar_reporte(json_data: Dict[str, Any], carpeta: Path, token: str) -> int:
    """
    Procesa el reporte JSON completo:
    1. Filtra CIs por tipo
    2. Valida NITs
    3. Enriquece datos
    4. Ejecuta eliminaciones
    
    Returns:
        int: Código de salida (EXIT_SUCCESS u otro)
    """
    logger.info("=" * 80)
    logger.info("PASO 5: PROCESAR REPORTE Y VALIDAR NITs")
    logger.info("=" * 80)
    
    # Filtrar CIs
    logger.info("Filtrando CIs por tipo 'clr_onyxservicecodes'...")
    cis_filtrados = filtrar_cis_por_tipo_servicecodes(json_data)
    logger.info(f"Total CIs filtrados: {len(cis_filtrados)}")
    
    # Validar NITs
    logger.info("Validando NITs en relaciones...")
    inconsistencias_normales, inconsistencias_particulares = validar_nit_en_relaciones_invertidas(json_data)
    logger.info(f"Inconsistencias normales: {len(inconsistencias_normales)}")
    logger.info(f"Inconsistencias particulares: {len(inconsistencias_particulares)}")
    
    # Preparar datos
    relations = json_data.get("relations", [])
    cis = json_data.get("cis", [])
    
    relations_by_id = {rel["ucmdbId"]: rel for rel in relations if rel.get("ucmdbId")}
    containment_by_end2 = {
        rel["end2Id"]: rel
        for rel in relations if rel.get("type") == "containment" and rel.get("end2Id")
    }
    cis_by_id = {ci.get("ucmdbId"): ci for ci in cis if ci.get("ucmdbId")}
    
    # Enriquecer inconsistencias NORMALES con relacion_fo
    relaciones_enriquecidas_normales = []
    for item in inconsistencias_normales:
        rel_id = item["ucmdbId"]
        rel_original = relations_by_id.get(rel_id)
        if not rel_original:
            continue
        
        end1id = rel_original.get("end1Id")
        end2id = rel_original.get("end2Id")
        if not end2id or not end1id:
            continue
        
        # Buscar relación FO
        containment_rel = containment_by_end2.get(end2id)
        ucmdbid_fo = None
        if containment_rel:
            sc_end1id = containment_rel.get("end1Id")
            ci_node = cis_by_id.get(sc_end1id)
            if ci_node and ci_node.get("type") == "clr_service_catalog_fo_e":
                ucmdbid_fo = containment_rel.get("ucmdbId")
        
        end1_node = cis_by_id.get(end1id)
        end2_node = cis_by_id.get(end2id)
        
        item_enriquecido = {
            "ucmdbId": item["ucmdbId"],
            "nit_end1": item.get("nit_end1"),
            "nit_end2": item.get("nit_end2"),
            "end1_ucmdbid": end1id,
            "end2_ucmdbid": end2id,
            "relacion_fo": bool(ucmdbid_fo),
            "ucmdbid_fo": ucmdbid_fo if ucmdbid_fo else "N/A",
            "end1_display_label": (end1_node.get("properties", {}).get("display_label") if end1_node else "N/A"),
            "end2_display_label": (end2_node.get("properties", {}).get("display_label") if end2_node else "N/A")
        }
        relaciones_enriquecidas_normales.append(item_enriquecido)
    
    # Enriquecer inconsistencias PARTICULARES
    relaciones_enriquecidas_particulares = []
    for item in inconsistencias_particulares:
        rel_id = item["ucmdbId"]
        rel_original = relations_by_id.get(rel_id)
        if not rel_original:
            continue
        
        end1id = rel_original.get("end1Id")
        end2id = rel_original.get("end2Id")
        if not end2id or not end1id:
            continue
        
        end1_node = cis_by_id.get(end1id)
        end2_node = cis_by_id.get(end2id)
        
        item_enriquecido = {
            "ucmdbId": item["ucmdbId"],
            "nit_end1": item.get("nit_end1"),
            "nit_end2": item.get("nit_end2"),
            "end1_ucmdbid": end1id,
            "end2_ucmdbid": end2id,
            "relacion_fo": False,
            "ucmdbid_fo": "N/A",
            "end1_display_label": (end1_node.get("properties", {}).get("display_label") if end1_node else "N/A"),
            "end2_display_label": (end2_node.get("properties", {}).get("display_label") if end2_node else "N/A")
        }
        relaciones_enriquecidas_particulares.append(item_enriquecido)
    
    # Guardar reportes
    logger.info("Guardando reportes...")
    guardar_inconsistencias_detalle(relaciones_enriquecidas_normales, carpeta, "inconsistencias.txt")
    guardar_inconsistencias_detalle(relaciones_enriquecidas_particulares, carpeta, "inconsistencias_particulares.txt")
    
    # PASO 6: Eliminaciones
    logger.info("\n")
    eliminar_en_ucmdb(token, relaciones_enriquecidas_normales, carpeta)
    
    # Filtrar y procesar ITSM (solo con relacion_fo: true)
    logger.info("\n")
    normales_con_fo = [
        item for item in relaciones_enriquecidas_normales
        if item.get("relacion_fo") and item.get("ucmdbid_fo") != "N/A"
    ]
    eliminar_en_itsm(normales_con_fo, carpeta)
    
    return EXIT_SUCCESS


# ==================== MAIN ====================

def main() -> int:
    """Función principal del script."""
    logger.info("=" * 80)
    logger.info("VALIDACIÓN DE CONSISTENCIA DE NITs EN UCMDB E ITSM")
    logger.info("=" * 80)
    logger.info(f"Modo ITSM: {MODO_EJECUCION.upper()}")
    
    # Validar que estamos en modo conocido
    if MODO_EJECUCION not in ["simulacion", "ejecucion"]:
        logger.error(f"ERROR: MODO_EJECUCION debe ser 'simulacion' o 'ejecucion', se encontró: {MODO_EJECUCION}")
        return EXIT_AUTH_ERROR
    
    if MODO_EJECUCION == "ejecucion":
        logger.warning("⚠️  MODO PRODUCCIÓN: Se ejecutarán DELETE reales en ambas APIs")
        logger.warning(f"⚠️  Credenciales ITSM verificadas: Usuario={ITSM_USERNAME}")
    else:
        logger.info("✓ Modo SIMULACIÓN: Las APIs no serán modificadas")
    
    logger.info("")
    
    # PASO 1: Autenticación
    logger.info("PASO 1: AUTENTICACIÓN EN UCMDB")
    logger.info("-" * 80)
    token = obtener_token_ucmdb()
    if not token:
        logger.error("No se pudo obtener el token")
        return EXIT_AUTH_ERROR
    logger.info("Autenticación exitosa\n")
    
    # PASO 2: Obtener reporte
    logger.info("PASO 2: OBTENER REPORTE DE UCMDB")
    logger.info("-" * 80)
    reporte = consultar_reporte_ucmdb(token)
    if not reporte:
        logger.error("No se pudo obtener el reporte")
        return EXIT_REPORT_ERROR
    logger.info("Reporte obtenido exitosamente\n")
    
    # PASO 3: Procesar JSON
    logger.info("PASO 3: PROCESAR JSON")
    logger.info("-" * 80)
    try:
        # Intentar parsear JSON como está
        json_data = json.loads(reporte)
    except json.JSONDecodeError as e:
        logger.warning(f"Primer intento de JSON falló: {e}")
        logger.info("Intentando recuperar JSON truncado...")
        try:
            # Si el JSON está truncado, intentar agregando cierre
            reporte_fixed = reporte
            
            # Contar [ abiertos vs ] cerrados
            open_brackets = reporte.count('[')
            close_brackets = reporte.count(']')
            open_braces = reporte.count('{')
            close_braces = reporte.count('}')
            
            if open_brackets > close_brackets:
                reporte_fixed += ']' * (open_brackets - close_brackets)
            if open_braces > close_braces:
                reporte_fixed += '}' * (open_braces - close_braces)
            
            json_data = json.loads(reporte_fixed)
            logger.info("JSON truncado recuperado exitosamente")
        except json.JSONDecodeError as e2:
            logger.error(f"JSON inválido incluso después de recuperación: {e2}")
            return EXIT_JSON_ERROR
    logger.info("JSON procesado exitosamente\n")
    
    # PASO 4: Crear carpeta
    logger.info("PASO 4: CREAR DIRECTORIO DE EJECUCIÓN")
    logger.info("-" * 80)
    carpeta_ejecucion = crear_directorio_ejecucion()
    guardar_reporte_json(json_data, carpeta_ejecucion)
    logger.info("")
    
    # PASO 5/6: Procesamiento y eliminaciones
    exit_code = procesar_reporte(json_data, carpeta_ejecucion, token)
    
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("EJECUCIÓN FINALIZADA")
    logger.info("=" * 80)
    
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\nEjecución interrumpida por el usuario")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        sys.exit(1)

