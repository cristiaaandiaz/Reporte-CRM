import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from auth import obtener_token_ucmdb
from report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    extraer_datos_relevantes_servicecodes,
    validar_nit_en_relaciones_invertidas,
    eliminar_relacion_ucmdb,
)
import requests
import base64

# Cargar variables de entorno
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ucmdb_validation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

REPORTS_BASE_DIR = "reports"

# CONTROL MANUAL - MODO DE EJECUCIÓN ITSM:
# - Si `MODO_ITSM = "simulacion"` => solo muestra qué se enviaría al API (DRY-RUN) - RECOMENDADO PRIMERO
# - Si `MODO_ITSM = "ejecucion"` => ejecuta realmente el DELETE en ITSM (PRODUCCIÓN)
MODO_ITSM = "simulacion"  # Cambiar a "ejecucion" cuando estés seguro

# CONTROL MANUAL - GENERACIÓN DE ARCHIVOS DE RESUMEN:
# - Si `GENERAR_RESUMEN = True` => genera resumen_itsm.txt con los resultados
# - Si `GENERAR_RESUMEN = False` => no genera el archivo de resumen
GENERAR_RESUMEN = False
# CONTROL MANUAL - CREACIÓN DE CARPETA DE EJECUCIÓN:
# - Si `CREAR_CARPETA_EJECUCION = True` => crea carpeta reports/ejecucion_TIMESTAMP con los archivos
# - Si `CREAR_CARPETA_EJECUCION = False` => no crea la carpeta de ejecución
CREAR_CARPETA_EJECUCION = False
# Configuración ITSM desde .env
ITSM_BASE_URL = os.getenv("ITSM_URL", "http://172.22.108.150:443/SM/9/rest/cirelationship1to1s")
ITSM_USERNAME = os.getenv("ITSM_USERNAME", "AUTOSM")
ITSM_PASSWORD = os.getenv("ITSM_PASSWORD", "4ut0SM2024.,")

EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 1
EXIT_REPORT_ERROR = 2
EXIT_JSON_ERROR = 3


def crear_directorio_ejecucion() -> Path:
    """
    Crea directorio de ejecución solo si CREAR_CARPETA_EJECUCION es True.
    Si está deshabilitado, devuelve un Path a un directorio temporal en memoria.
    """
    if not CREAR_CARPETA_EJECUCION:
        logger.info("Creación de carpeta de ejecución deshabilitada (CREAR_CARPETA_EJECUCION=False)")
        # Retorna un Path ficticio que no será usado para guardar archivos
        return Path(REPORTS_BASE_DIR) / "disabled"
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = Path(REPORTS_BASE_DIR) / f"ejecucion_{timestamp}"
    carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
    return carpeta_ejecucion


def guardar_reporte_json(
    json_data: Dict[str, Any],
    carpeta: Path
) -> Optional[Path]:
    # No guardar si la carpeta está deshabilitada
    if carpeta.name == "disabled":
        logger.info("Guardado de reporte JSON deshabilitado (CREAR_CARPETA_EJECUCION=False)")
        return None
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archivo_reporte = carpeta / f"reporte_{timestamp}.json"
    try:
        with open(archivo_reporte, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Reporte completo guardado en: {archivo_reporte}")
        return archivo_reporte
    except IOError as e:
        logger.error(f"Error al guardar el reporte: {e}")
        return None


def guardar_inconsistencias_detalle(
    inconsistencias: List[Dict[str, Any]],
    carpeta: Path,
    nombre_archivo: str,
) -> Optional[Path]:
    if not inconsistencias:
        logger.info(f"No se encontraron inconsistencias en {nombre_archivo}. No se generó archivo.")
        return None

    # No guardar si la carpeta está deshabilitada
    if carpeta.name == "disabled":
        logger.info(f"Guardado de {nombre_archivo} deshabilitado (CREAR_CARPETA_EJECUCION=False)")
        return None

    archivo = carpeta / nombre_archivo

    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(f"Reporte detallado de Inconsistencias de NITs\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write(f"Total: {len(inconsistencias)}\n")
            f.write("=" * 50 + "\n\n")

            for i, item in enumerate(inconsistencias, start=1):
                f.write(f"{i}. ucmdbId: {item['ucmdbId']}\n")
                f.write(f"    NIT end1 (ucmdbId): {item.get('nit_end1', 'N/A')} ({item.get('end1_ucmdbid', 'N/A')} - {item.get('end1_display_label', 'N/A')})\n")
                f.write(f"    NIT end2 (ucmdbId): {item.get('nit_end2', 'N/A')} ({item.get('end2_ucmdbid', 'N/A')} - {item.get('end2_display_label', 'N/A')})\n")
                f.write(f"    relacion fo: {'true' if item.get('relacion_fo') else 'false'}\n")
                f.write(f"    ucmdbid_fo: {item.get('ucmdbid_fo', 'N/A')}\n\n")

        logger.info(f"Inconsistencias guardadas en: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error al guardar inconsistencias en {nombre_archivo}: {e}")
        return None


def guardar_ids_simulados(ids: List[str], carpeta: Path) -> Optional[Path]:
    """
    Guarda los IDs que se van a eliminar en producción.
    Esto sirve para validar después que se eliminaron los correctos.
    """
    # No guardar si la carpeta está deshabilitada
    if carpeta.name == "disabled":
        logger.info("Guardado de IDs deshabilitado (CREAR_CARPETA_EJECUCION=False)")
        return None
    
    archivo = carpeta / "ids_a_eliminar_en_produccion.txt"
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("IDs programados para eliminar en PRODUCCIÓN\n")
            f.write(f"Fecha dry_run: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")
            for i, rid in enumerate(ids, 1):
                f.write(f"{i}. {rid}\n")
        logger.info(f"IDs guardados para validación en: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error al guardar IDs: {e}")
        return None


def eliminar_inconsistencias_normales_y_fo(
    token: str,
    inconsistencias_normales: List[Dict[str, Any]],
    carpeta: Path,
    modo_itsm: str = "simulacion"
) -> None:
    """
    Procesa inconsistencias que tengan relacion_fo: true
    y ejecuta/simula el DELETE en ITSM.
    
    Args:
        token: Token de autenticación UCMDB (no se usa en ITSM pero se mantiene para compatibilidad)
        inconsistencias_normales: Lista de inconsistencias
        carpeta: Carpeta para guardar resumen
        modo_itsm: "simulacion" (DRY-RUN) o "ejecucion" (producción)
    """
    logger.info("=" * 60)
    logger.info("Procesando inconsistencias con relacion fo: true")
    logger.info(f"Modo ITSM: {modo_itsm.upper()}")
    logger.info("=" * 60)

    # Filtrar solo las que tienen relacion_fo: true
    inconsistencias_con_fo = [
        item for item in inconsistencias_normales
        if item.get("relacion_fo") and item.get("ucmdbid_fo") != "N/A"
    ]

    logger.info(f"Total de inconsistencias con relacion fo: {len(inconsistencias_con_fo)}")

    if not inconsistencias_con_fo:
        logger.info("No hay inconsistencias con relacion fo para procesar.")
        return

    resumen_itsm = []

    if modo_itsm == "simulacion":
        logger.warning("[SIMULACIÓN] Se mostrarán las llamadas que se harían al API ITSM")
        logger.warning("-" * 60)
        
        for idx, item in enumerate(inconsistencias_con_fo, 1):
            ucmdbid = item["ucmdbId"]
            ucmdbid_fo = item["ucmdbid_fo"]
            
            # Construir URL del DELETE (primero el ucmdbid_fo, luego el ucmdbid)
            url = f"{ITSM_BASE_URL}/{ucmdbid_fo}/{ucmdbid}"
            
            logger.warning(f"\n{idx}. SIMULACIÓN de DELETE en ITSM")
            logger.warning(f"   URL: {url}")
            logger.warning(f"   Método: DELETE")
            logger.warning(f"   Auth: Basic Auth ({ITSM_USERNAME}/***)")
            logger.warning(f"   ucmdbId: {ucmdbid}")
            logger.warning(f"   ucmdbid_fo: {ucmdbid_fo}")
            logger.warning(f"   Timeout: 30s")
            
            resumen_itsm.append({
                "numero": idx,
                "ucmdbId": ucmdbid,
                "ucmdbid_fo": ucmdbid_fo,
                "url": url,
                "modo": "SIMULADO",
                "estado": "Listo para ejecutarse"
            })
        
        logger.warning("-" * 60)
        logger.warning(f"\nTotal de llamadas a ITSM (simuladas): {len(inconsistencias_con_fo)}")
        logger.warning("\n⚠️ Esto es una SIMULACIÓN. No se eliminó nada en ITSM.")
        logger.warning("⚠️ Cuando estés seguro, cambia MODO_ITSM a 'ejecucion' en línea 36\n")
        
    elif modo_itsm == "ejecucion":
        logger.critical("=" * 60)
        logger.critical("⚠️ MODO PRODUCCIÓN: Ejecutando DELETE en ITSM")
        logger.critical("=" * 60)
        
        for idx, item in enumerate(inconsistencias_con_fo, 1):
            ucmdbid = item["ucmdbId"]
            ucmdbid_fo = item["ucmdbid_fo"]
            url = f"{ITSM_BASE_URL}/{ucmdbid_fo}/{ucmdbid}"
            
            logger.warning(f"\n{idx}. DELETE en ITSM")
            logger.warning(f"   URL: {url}")
            
            exito, mensaje = ejecutar_delete_itsm(url)
            
            if exito:
                logger.info(f"   ✓ Eliminada exitosamente")
                resumen_itsm.append({
                    "numero": idx,
                    "ucmdbId": ucmdbid,
                    "ucmdbid_fo": ucmdbid_fo,
                    "url": url,
                    "modo": "EJECUTADO",
                    "estado": "Éxito",
                    "mensaje": mensaje
                })
            else:
                logger.error(f"   ✗ FALLO: {mensaje}")
                resumen_itsm.append({
                    "numero": idx,
                    "ucmdbId": ucmdbid,
                    "ucmdbid_fo": ucmdbid_fo,
                    "url": url,
                    "modo": "EJECUTADO",
                    "estado": "Fallo",
                    "mensaje": mensaje
                })
    
    # Guardar resumen
    guardar_resumen_itsm(resumen_itsm, carpeta, modo_itsm)


def ejecutar_delete_itsm(url: str) -> tuple[bool, str]:
    """
    Ejecuta DELETE en ITSM con reintentos.
    
    Returns:
        Tupla (éxito: bool, mensaje: str)
    """
    # Crear header de autenticación Basic Auth
    credenciales = f"{ITSM_USERNAME}:{ITSM_PASSWORD}"
    credenciales_encoded = base64.b64encode(credenciales.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {credenciales_encoded}",
        "Content-Type": "application/json"
    }
    
    max_reintentos = 3
    delay_reintento = 2
    
    for intento in range(1, max_reintentos + 1):
        try:
            logger.info(f"   Intento {intento}/{max_reintentos}...")
            
            response = requests.delete(
                url,
                headers=headers,
                verify=False,
                timeout=30
            )
            
            logger.info(f"   Respuesta HTTP: {response.status_code}")
            
            # Códigos de éxito
            if response.status_code in [200, 202, 204]:
                return True, f"HTTP {response.status_code}"
            
            # Error permanente (4xx) - no reintentar
            if 400 <= response.status_code < 500:
                return False, f"Error permanente HTTP {response.status_code}"
            
            # Error temporal (5xx) - reintentar
            if 500 <= response.status_code < 600:
                if intento < max_reintentos:
                    logger.warning(f"   Error servidor (HTTP {response.status_code}), reintentando...")
                    import time
                    time.sleep(delay_reintento)
                    continue
                else:
                    return False, f"Error servidor HTTP {response.status_code} después de {max_reintentos} intentos"
        
        except requests.exceptions.Timeout:
            logger.warning(f"   Timeout, reintentando...")
            if intento < max_reintentos:
                import time
                time.sleep(delay_reintento)
                continue
            return False, f"Timeout después de {max_reintentos} intentos"
        
        except Exception as e:
            logger.error(f"   Error: {e}")
            if intento < max_reintentos:
                import time
                time.sleep(delay_reintento)
                continue
            return False, str(e)
    
    return False, "Error desconocido"


def guardar_resumen_itsm(
    resumen: List[Dict[str, Any]],
    carpeta: Path,
    modo_itsm: str
) -> Optional[Path]:
    """
    Guarda resumen de las operaciones ITSM.
    Solo genera el archivo si GENERAR_RESUMEN es True.
    """
    if not GENERAR_RESUMEN:
        logger.info("Generación de resumen ITSM deshabilitada (GENERAR_RESUMEN=False)")
        return None
    
    # No guardar si la carpeta está deshabilitada
    if carpeta.name == "disabled":
        logger.info("Guardado de resumen ITSM deshabilitado (CREAR_CARPETA_EJECUCION=False)")
        return None
    
    archivo = carpeta / "resumen_itsm.txt"
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            modo_titulo = "SIMULACIÓN" if modo_itsm == "simulacion" else "EJECUCIÓN"
            f.write(f"Resumen de Operaciones ITSM - {modo_titulo}\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write(f"Modo: {modo_itsm.upper()}\n")
            f.write("=" * 80 + "\n\n")
            
            for item in resumen:
                f.write(f"{item['numero']}. ucmdbId: {item['ucmdbId']}\n")
                f.write(f"   ucmdbid_fo: {item['ucmdbid_fo']}\n")
                f.write(f"   URL: {item['url']}\n")
                f.write(f"   Estado: {item['estado']}\n")
                if "mensaje" in item:
                    f.write(f"   Mensaje: {item['mensaje']}\n")
                f.write("\n")
        
        logger.info(f"Resumen ITSM guardado en: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error al guardar resumen ITSM: {e}")
        return None


def guardar_resumen_eliminacion_detallado(
    resumen: List[Dict[str, Any]],
    carpeta: Path,
    dry_run: bool = True
) -> Optional[Path]:
    """
    Guarda un resumen detallado de las eliminaciones UCMDB (función obsoleta, se mantiene para compatibilidad).
    """
    # No guardar si la carpeta está deshabilitada
    if carpeta.name == "disabled":
        logger.info("Guardado de resumen de eliminación deshabilitado (CREAR_CARPETA_EJECUCION=False)")
        return None
    
    archivo = carpeta / "resumen_eliminacion.txt"

    try:
        with open(archivo, "w", encoding="utf-8") as f:
            modo = "[DRY RUN - SIMULACIÓN]" if dry_run else "[EJECUCIÓN REAL]"
            f.write(f"Resumen de Eliminación de Relaciones Inconsistentes {modo}\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")

            for item in resumen:
                f.write(f"{item['numero']}. Relación Principal: {item['ucmdbId_principal']}\n")
                if item['ucmdbId_fo']:
                    f.write(f"   Relación FO: {item['ucmdbId_fo']}\n")
                f.write("   IDs a Eliminar:\n")
                for elim in item["ids_eliminados"]:
                    estado = "✓ (Simulado)" if elim["simulado"] else ("✓" if elim["exito"] else "✗")
                    f.write(f"     - {elim['ucmdbId']}: {estado}\n")
                f.write("\n")

        logger.info(f"Resumen de eliminación guardado en: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error al guardar resumen de eliminación: {e}")
        return None


def procesar_reporte(json_data: Dict[str, Any], carpeta: Path, token: str) -> int:
    logger.info("Filtrando objetos de tipo 'clr_onyxservicecodes'...")
    cis_filtrados = filtrar_cis_por_tipo_servicecodes(json_data)
    cis_log = extraer_datos_relevantes_servicecodes(cis_filtrados)

    logger.info(f"Total de objetos filtrados: {len(cis_log)}")

    logger.info("Validando NITs en relaciones...")
    inconsistencias_normales, inconsistencias_particulares = validar_nit_en_relaciones_invertidas(json_data)

    logger.info(f"Relaciones con NIT diferentes encontradas (normales): {len(inconsistencias_normales)}")
    logger.info(f"Relaciones con NIT diferentes encontradas (particulares): {len(inconsistencias_particulares)}")

    relations = json_data.get("relations", [])
    cis = json_data.get("cis", [])

    relations_by_id = {rel["ucmdbId"]: rel for rel in relations if rel.get("ucmdbId")}
    containment_by_end2 = {
        rel["end2Id"]: rel
        for rel in relations if rel.get("type") == "containment" and rel.get("end2Id")
    }
    cis_by_id = {ci.get("ucmdbId"): ci for ci in cis if ci.get("ucmdbId")}

    relaciones_fo_para_agregar = []

    # Procesar inconsistencias NORMALES
    for item in inconsistencias_normales:
        rel_id = item["ucmdbId"]
        rel_original = relations_by_id.get(rel_id)
        if not rel_original:
            continue
        end1id = rel_original.get("end1Id")
        end2id = rel_original.get("end2Id")
        if not end2id or not end1id:
            continue

        containment_rel = containment_by_end2.get(end2id)
        ucmdbid_fo = None
        if containment_rel:
            sc_end1id = containment_rel.get("end1Id")
            ci_node = cis_by_id.get(sc_end1id)
            if ci_node and ci_node.get("type") == "clr_service_catalog_fo_e":
                ucmdbid_fo = containment_rel.get("ucmdbId")

        item_actualizado = {
            "ucmdbId": item["ucmdbId"],
            "nit_end1": item.get("nit_end1"),
            "nit_end2": item.get("nit_end2"),
            "end1_ucmdbid": end1id,
            "end2_ucmdbid": end2id,
            "relacion_fo": bool(ucmdbid_fo),
            "ucmdbid_fo": ucmdbid_fo if ucmdbid_fo else "N/A"
        }

        # Añadir display_label de nodos
        end1_node = cis_by_id.get(end1id)
        end2_node = cis_by_id.get(end2id)
        item_actualizado["end1_display_label"] = (end1_node.get("properties", {}).get("display_label") if end1_node else "N/A")
        item_actualizado["end2_display_label"] = (end2_node.get("properties", {}).get("display_label") if end2_node else "N/A")

        relaciones_fo_para_agregar.append(item_actualizado)

    inconsistencias_normales[:] = relaciones_fo_para_agregar

    # Procesar inconsistencias PARTICULARES
    relaciones_particulares_enriquecidas = []
    for item in inconsistencias_particulares:
        rel_id = item["ucmdbId"]
        rel_original = relations_by_id.get(rel_id)
        if not rel_original:
            continue
        end1id = rel_original.get("end1Id")
        end2id = rel_original.get("end2Id")
        if not end2id or not end1id:
            continue

        item_actualizado = {
            "ucmdbId": item["ucmdbId"],
            "nit_end1": item.get("nit_end1"),
            "nit_end2": item.get("nit_end2"),
            "end1_ucmdbid": end1id,
            "end2_ucmdbid": end2id,
            "relacion_fo": False,
            "ucmdbid_fo": "N/A"
        }

        # Añadir display_label de nodos
        end1_node = cis_by_id.get(end1id)
        end2_node = cis_by_id.get(end2id)
        item_actualizado["end1_display_label"] = (end1_node.get("properties", {}).get("display_label") if end1_node else "N/A")
        item_actualizado["end2_display_label"] = (end2_node.get("properties", {}).get("display_label") if end2_node else "N/A")

        relaciones_particulares_enriquecidas.append(item_actualizado)

    inconsistencias_particulares[:] = relaciones_particulares_enriquecidas

    # Logs estructurados y legibles para inconsistencias normales
    if inconsistencias_normales:
        logger.warning("Se detectaron inconsistencias normales:")
        for i, item in enumerate(inconsistencias_normales, 1):
            logger.warning(f"{i}. ucmdbId: {item['ucmdbId']}")
            logger.warning(f"   NIT end1 (ucmdbId): {item.get('nit_end1', 'N/A')} ({item.get('end1_ucmdbid', 'N/A')} - {item.get('end1_display_label', 'N/A')})")
            logger.warning(f"   NIT end2 (ucmdbId): {item.get('nit_end2', 'N/A')} ({item.get('end2_ucmdbid', 'N/A')} - {item.get('end2_display_label', 'N/A')})")
            logger.warning(f"   relacion fo: {'true' if item.get('relacion_fo') else 'false'}")
            logger.warning(f"   ucmdbid_fo: {item.get('ucmdbid_fo', 'N/A')}")
            logger.warning("")

    # Logs para inconsistencias particulares
    if inconsistencias_particulares:
        logger.warning("Se detectaron inconsistencias particulares:")
        for i, item in enumerate(inconsistencias_particulares, 1):
            logger.warning(f"{i}. ucmdbId: {item['ucmdbId']}")
            logger.warning(f"   NIT end1 (ucmdbId): {item.get('nit_end1', 'N/A')} ({item.get('end1_ucmdbid', 'N/A')} - {item.get('end1_display_label', 'N/A')})")
            logger.warning(f"   NIT end2 (ucmdbId): {item.get('nit_end2', 'N/A')} ({item.get('end2_ucmdbid', 'N/A')} - {item.get('end2_display_label', 'N/A')})")
            logger.warning("")

    # Guardar archivos txt con formato detallado
    guardar_inconsistencias_detalle(inconsistencias_normales, carpeta, "inconsistencias.txt")
    guardar_inconsistencias_detalle(inconsistencias_particulares, carpeta, "inconsistencias_particulares.txt")

    # Procesar inconsistencias con relacion_fo: true
    # Pasar el MODO_ITSM configurado arriba
    eliminar_inconsistencias_normales_y_fo(token, inconsistencias_normales, carpeta, modo_itsm=MODO_ITSM)

    return EXIT_SUCCESS


def main() -> int:
    logger.info("=" * 60)
    logger.info("Iniciando validación de consistencia de NITs en UCMDB")
    logger.info(f"Modo ITSM: {MODO_ITSM}")
    logger.info("=" * 60)

    logger.info("Paso 1/4: Autenticando con UCMDB...")
    token = obtener_token_ucmdb()

    if not token:
        logger.error("No se pudo obtener el token. Finalizando ejecución.")
        return EXIT_AUTH_ERROR

    logger.info("Autenticación exitosa")

    logger.info("Paso 2/4: Consultando reporte de contratos CRM...")
    reporte = consultar_reporte_ucmdb(token)

    if not reporte:
        logger.error("No se pudo obtener el reporte. Finalizando ejecución.")
        return EXIT_REPORT_ERROR

    logger.info("Reporte obtenido exitosamente")

    logger.info("Paso 3/4: Procesando datos JSON...")
    try:
        json_data = json.loads(reporte)
    except json.JSONDecodeError as e:
        logger.error(f"El contenido del reporte no es un JSON válido: {e}")
        return EXIT_JSON_ERROR

    carpeta_ejecucion = crear_directorio_ejecucion()
    guardar_reporte_json(json_data, carpeta_ejecucion)

    logger.info("Paso 4/4: Validando datos y generando reportes...")
    exit_code = procesar_reporte(json_data, carpeta_ejecucion, token)

    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\nEjecución interrumpida por el usuario")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Error inesperado durante la ejecución: {e}")
        sys.exit(1)
