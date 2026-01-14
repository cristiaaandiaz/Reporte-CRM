import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from auth import obtener_token_ucmdb
from report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    extraer_datos_relevantes_servicecodes,
    validar_nit_en_relaciones_invertidas,
    eliminar_relacion_ucmdb,
)

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

# CONTROL MANUAL (CAMBIA SÓLO ESTA LÍNEA):
# - Si `ELIMINAR_RELACIONES = True` => se eliminarán las relaciones usando la API (ejecución REAL).
# - Si `ELIMINAR_RELACIONES = False` => se simula la eliminación (DRY-RUN). Esto es lo recomendado para pruebas.
ELIMINAR_RELACIONES = False

EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 1
EXIT_REPORT_ERROR = 2
EXIT_JSON_ERROR = 3


def crear_directorio_ejecucion() -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = Path(REPORTS_BASE_DIR) / f"ejecucion_{timestamp}"
    carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
    return carpeta_ejecucion


def guardar_reporte_json(
    json_data: Dict[str, Any],
    carpeta: Path
) -> Optional[Path]:
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
    dry_run: bool = True
) -> None:
    """
    Elimina inconsistencias normales y sus relaciones FO asociadas.
    
    Args:
        token: Token de autenticación
        inconsistencias_normales: Lista de inconsistencias a eliminar
        carpeta: Carpeta para guardar resumen
        dry_run: Si True, simula la eliminación sin hacer llamadas reales al API
    """
    logger.info("=" * 60)
    if dry_run:
        logger.info("[DRY RUN] Simulando eliminación de inconsistencias normales")
    else:
        logger.critical("⚠️ [PRODUCCIÓN] Eliminando inconsistencias normales REALES")
    logger.info("=" * 60)

    total_eliminadas = 0
    resumen_eliminaciones = []
    ids_a_eliminar_en_produccion = []  # Rastrear IDs simulados

    for idx, item in enumerate(inconsistencias_normales, 1):
        rel_id = item["ucmdbId"]
        ucmdbid_fo = item.get("ucmdbid_fo")
        lista_ids = [rel_id]

        if ucmdbid_fo and ucmdbid_fo != "N/A":
            lista_ids.append(ucmdbid_fo)

        resultado_item = {
            "numero": idx,
            "ucmdbId_principal": rel_id,
            "ucmdbId_fo": ucmdbid_fo if ucmdbid_fo != "N/A" else None,
            "ids_eliminados": []
        }

        logger.warning(f"{idx}. Procesando relación: {rel_id}")
        
        for rid in lista_ids:
            if dry_run:
                # Simulación: solo loguea, no elimina
                logger.info(f"   [DRY RUN] Se eliminaría: {rid}")
                ids_a_eliminar_en_produccion.append(rid)  # Registra para validación
                resultado_item["ids_eliminados"].append({
                    "ucmdbId": rid,
                    "exito": True,
                    "simulado": True
                })
            else:
                # Eliminación real - CON VALIDACIÓN
                try:
                    exito = eliminar_relacion_ucmdb(token, rid)
                    if not isinstance(exito, bool):
                        logger.error(f"   ¡ERROR! eliminar_relacion_ucmdb retornó {type(exito).__name__} en lugar de bool: {rid}")
                        exito = False
                    
                    resultado_item["ids_eliminados"].append({
                        "ucmdbId": rid,
                        "exito": exito,
                        "simulado": False
                    })
                    if exito:
                        logger.info(f"   ✓ Eliminada: {rid}")
                    else:
                        logger.error(f"   ✗ FALLO al eliminar: {rid}")
                except Exception as e:
                    logger.error(f"   ✗ EXCEPCIÓN al eliminar {rid}: {e}")
                    resultado_item["ids_eliminados"].append({
                        "ucmdbId": rid,
                        "exito": False,
                        "simulado": False,
                        "error": str(e)
                    })

        resumen_eliminaciones.append(resultado_item)
        total_eliminadas += 1

    logger.info("=" * 60)
    logger.info(f"Total de procesos de eliminación: {total_eliminadas}")
    logger.info("=" * 60)

    # Guardar resumen
    guardar_resumen_eliminacion_detallado(resumen_eliminaciones, carpeta, dry_run)
    
    # Guardar lista de IDs simulados para comparar después en producción
    if dry_run:
        guardar_ids_simulados(ids_a_eliminar_en_produccion, carpeta)


def guardar_resumen_eliminacion_detallado(
    resumen: List[Dict[str, Any]],
    carpeta: Path,
    dry_run: bool = True
) -> Optional[Path]:
    """
    Guarda un resumen detallado de las eliminaciones.
    """
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

    # Configurar modo a partir de la constante `ELIMINAR_RELACIONES` (línea única arriba)
    # dry_run_mode == True -> solo simula; False -> realiza llamadas DELETE
    dry_run_mode = not ELIMINAR_RELACIONES

    if not dry_run_mode:
        logger.critical("\n" + "⚠️ " * 30)
        logger.critical("¡ADVERTENCIA! MODO PRODUCCIÓN ACTIVADO")
        logger.critical("Se eliminarán relaciones REALES en UCMDB")
        logger.critical("⚠️ " * 30 + "\n")

    eliminar_inconsistencias_normales_y_fo(token, inconsistencias_normales, carpeta, dry_run=dry_run_mode)

    return EXIT_SUCCESS


def main() -> int:
    # Control manual: cambia la constante ELIMINAR_RELACIONES arriba en el archivo
    final_enable = ELIMINAR_RELACIONES

    logger.info("=" * 60)
    logger.info("Iniciando validación de consistencia de NITs en UCMDB")
    logger.info(f"Modo eliminaciones reales: {'ENABLED' if final_enable else 'DRY-RUN'}")
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
