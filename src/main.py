"""
Orquestador principal del flujo de validación de NITs.
"""

import sys
import json
from pathlib import Path
from typing import Optional

from .config import (
    ExecutionFlags,
    ExitCodes,
    ReportConfig,
    ReportGenerationConfig,
    validar_configuracion_inicial
)
from .logger_config import obtener_logger
from .auth import obtener_token_ucmdb
from .report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    validar_nit_en_relaciones_invertidas,
    validar_relaciones_usage_de_servicecodes
)
from .processor import (
    crear_directorio_ejecucion,
    validar_integridad_json,
    guardar_reporte_json,
    guardar_inconsistencias_detalle,
    enriquecer_inconsistencias_normales,
    guardar_relaciones_usage_detalle
)
from .ucmdb_operations import eliminar_en_ucmdb, eliminar_relaciones_usage_de_servicecodes
from .itsm_operations import eliminar_en_itsm

logger = obtener_logger(__name__)


def procesar_reporte(json_data: dict, carpeta: Path, token: Optional[str]) -> int:
    """Procesa el reporte JSON: filtra, valida NITs, elimina."""
    logger.info("=" * 80)
    logger.info("PASO 5: PROCESAR REPORTE Y VALIDAR NITs")
    logger.info("=" * 80)
    
    logger.info("Filtrando CIs por tipo 'clr_onyxservicecodes'...")
    cis_filtrados = filtrar_cis_por_tipo_servicecodes(json_data)
    logger.info(f"Total CIs filtrados: {len(cis_filtrados)}")
    
    logger.info("Validando NITs en relaciones...")
    inconsistencias_normales, inconsistencias_particulares = validar_nit_en_relaciones_invertidas(json_data)
    logger.info(f"Inconsistencias normales: {len(inconsistencias_normales)}")
    
    logger.info("\nValidando relaciones usage...")
    relaciones_usage_a_eliminar = validar_relaciones_usage_de_servicecodes(json_data)
    logger.info(f"Relaciones usage a eliminar: {len(relaciones_usage_a_eliminar)}")
    
    relations = json_data.get("relations", [])
    cis = json_data.get("cis", [])
    
    containment_by_end2 = {
        rel["end2Id"]: rel
        for rel in relations if rel.get("type") == "containment" and rel.get("end2Id")
    }
    cis_by_id = {ci.get("ucmdbId"): ci for ci in cis if ci.get("ucmdbId")}
    
    logger.info("Enriqueciendo inconsistencias...")
    relaciones_enriquecidas_normales = enriquecer_inconsistencias_normales(
        inconsistencias_normales,
        relations,
        containment_by_end2,
        cis_by_id
    )
    
    logger.info("Guardando reportes detallados...")
    if ReportGenerationConfig.INCONSISTENCIAS:
        guardar_inconsistencias_detalle(relaciones_enriquecidas_normales, carpeta, "inconsistencias.txt")
    
    if relaciones_usage_a_eliminar:
        guardar_relaciones_usage_detalle(relaciones_usage_a_eliminar, carpeta, "relaciones_usage_de_servicecodes.txt")
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 6A: ELIMINAR EN UCMDB (NITs)")
    logger.info("=" * 80)
    eliminar_en_ucmdb(
        token,
        relaciones_enriquecidas_normales,
        carpeta,
        modo_ejecucion=ExecutionFlags.MODO_EJECUCION,
        generar_resumen=ReportGenerationConfig.RESUMEN_UCMDB
    )
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 6B: ELIMINAR RELACIONES USAGE EN UCMDB")
    logger.info("=" * 80)
    if relaciones_usage_a_eliminar:
        eliminar_relaciones_usage_de_servicecodes(
            token,
            relaciones_usage_a_eliminar,
            carpeta,
            modo_ejecucion=ExecutionFlags.MODO_EJECUCION,
            generar_resumen=ReportGenerationConfig.RESUMEN_UCMDB
        )
    else:
        logger.info("No hay relaciones usage para procesar")
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 6C: ACTUALIZAR EN ITSM")
    logger.info("=" * 80)
    normales_con_fo = [
        item for item in relaciones_enriquecidas_normales
        if item.get("relacion_fo") and item.get("ucmdbid_fo") != "N/A"
    ]
    eliminar_en_itsm(
        normales_con_fo,
        carpeta,
        modo_ejecucion=ExecutionFlags.MODO_EJECUCION,
        generar_resumen=ReportGenerationConfig.RESUMEN_ITSM,
        cis_by_id=cis_by_id
    )
    
    return ExitCodes.SUCCESS


def main() -> int:
    """Función principal del script."""
    logger.info("=" * 80)
    logger.info("VALIDACIÓN DE CONSISTENCIA DE NITs EN UCMDB E ITSM")
    logger.info("=" * 80)
    logger.info(f"Modo: {ExecutionFlags.MODO_EJECUCION.upper()}")
    
    try:
        validar_configuracion_inicial()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return ExitCodes.CONFIG_ERROR
    
    if ExecutionFlags.MODO_EJECUCION == "ejecucion":
        logger.warning("⚠️ MODO EJECUCIÓN - Se realizarán cambios reales")
    else:
        logger.info("ℹ️ MODO SIMULACIÓN - Sin cambios reales")
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 1: AUTENTICACIÓN UCMDB")
    logger.info("=" * 80)
    
    token: Optional[str] = None
    
    if not ExecutionFlags.USAR_REPORTE_LOCAL or ExecutionFlags.MODO_EJECUCION == "ejecucion":
        logger.info("Obteniendo token de autenticación...")
        token = obtener_token_ucmdb()
        
        if not token:
            logger.error("Falló autenticación con UCMDB")
            return ExitCodes.AUTH_ERROR
        
        logger.info("✓ Token obtenido")
    else:
        logger.info("Token no requerido (modo simulación con reporte local)")
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 2: OBTENER REPORTE")
    logger.info("=" * 80)
    
    reporte_contenido: Optional[str] = None
    
    if ExecutionFlags.USAR_REPORTE_LOCAL:
        logger.info(f"Cargando reporte local: {ReportConfig.RUTA_REPORTE_LOCAL}")
        try:
            with open(ReportConfig.RUTA_REPORTE_LOCAL, "r", encoding="utf-8") as f:
                reporte_contenido = f.read()
            logger.info("✓ Reporte local cargado")
        except FileNotFoundError:
            logger.error(f"Archivo no encontrado: {ReportConfig.RUTA_REPORTE_LOCAL}")
            return ExitCodes.REPORT_ERROR
        except IOError as e:
            logger.error(f"Error leyendo reporte: {e}")
            return ExitCodes.REPORT_ERROR
    else:
        logger.info("Consultando reporte desde API UCMDB...")
        try:
            reporte_contenido = consultar_reporte_ucmdb(token)
            if not reporte_contenido:
                logger.error("No se obtuvo contenido del reporte")
                return ExitCodes.REPORT_ERROR
            logger.info("✓ Reporte obtenido desde API")
        except Exception as e:
            logger.error(f"Error al consultar reporte: {e}")
            return ExitCodes.REPORT_ERROR
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 3: PROCESAR JSON")
    logger.info("=" * 80)
    
    try:
        json_data = json.loads(reporte_contenido)
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON: {e}")
        logger.error(f"  Posición: línea {e.lineno}, columna {e.colno}")
        
        if isinstance(reporte_contenido, str):
            tamanio_mb = len(reporte_contenido) / (1024 * 1024)
            logger.error(f"  Tamaño: {tamanio_mb:.2f} MB")
            if tamanio_mb > 100:
                logger.error("⚠️ El JSON muy grande puede estar truncado")
        
        return ExitCodes.JSON_ERROR
    
    logger.info("✓ JSON procesado\n")
    
    if not validar_integridad_json(json_data):
        logger.error("Validación de integridad falló")
        return ExitCodes.JSON_ERROR
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 4: CREAR DIRECTORIO DE EJECUCIÓN")
    logger.info("=" * 80)
    
    carpeta_ejecucion = crear_directorio_ejecucion(ExecutionFlags.CREAR_CARPETA_EJECUCION)
    
    if ReportGenerationConfig.REPORTE_JSON:
        guardar_reporte_json(json_data, carpeta_ejecucion)
    
    logger.info("\n" + "=" * 80)
    logger.info("PASO 5-6: PROCESAMIENTO Y ELIMINACIONES")
    logger.info("=" * 80)
    
    exit_code = procesar_reporte(json_data, carpeta_ejecucion, token)
    
    logger.info("\n" + "=" * 80)
    logger.info("EJECUCIÓN FINALIZADA")
    logger.info("=" * 80)
    
    return exit_code


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\nEjecución cancelada por el usuario")
        sys.exit(ExitCodes.EXECUTION_ERROR)
    except Exception as e:
        logger.exception(f"Error crítico: {e}")
        sys.exit(ExitCodes.EXECUTION_ERROR)