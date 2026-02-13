"""
Script de Validación de Consistencia de NITs en UCMDB e ITSM.

Proporciona funcionalidad completa para:
1. Autenticar contra UCMDB
2. Obtener un reporte JSON de relaciones
3. Validar la consistencia de NITs
4. Simular o ejecutar eliminaciones en UCMDB e ITSM

Configuración controlada por flags en src/config.py:
- MODO_EJECUCION: "simulacion" (DRY-RUN) o "ejecucion" (real)
- USAR_REPORTE_LOCAL: True (JSON local) o False (API UCMDB)
- GENERAR_RESUMEN: True para generar archivos de resumen
- CREAR_CARPETA_EJECUCION: True para crear carpeta con timestamp
"""

import sys
import json
from pathlib import Path

from .config import (
    ExecutionFlags,
    ExitCodes,
    ReportConfig,
    validar_configuracion_inicial
)
from .logger_config import obtener_logger
from .auth import obtener_token_ucmdb
from .report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    validar_nit_en_relaciones_invertidas
)
from .processor import (
    crear_directorio_ejecucion,
    validar_integridad_json,
    guardar_reporte_json,
    guardar_inconsistencias_detalle,
    enriquecer_inconsistencias_normales,
    enriquecer_inconsistencias_particulares
)
from .ucmdb_operations import eliminar_en_ucmdb
from .itsm_operations import eliminar_en_itsm

logger = obtener_logger(__name__)


def procesar_reporte(json_data: dict, carpeta: Path, token: str) -> int:
    """
    Procesa el reporte JSON completo:
    
    1. Filtra CIs por tipo
    2. Valida NITs
    3. Enriquece datos
    4. Ejecuta eliminaciones
    
    Args:
        json_data: Datos JSON descargados
        carpeta: Carpeta para guardar resultados
        token: Token JWT de UCMDB
    
    Returns:
        Código de salida (EXIT_SUCCESS u otro)
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
    
    # Preparar índices para enriquecimiento
    relations = json_data.get("relations", [])
    cis = json_data.get("cis", [])
    
    relations_by_id = {rel["ucmdbId"]: rel for rel in relations if rel.get("ucmdbId")}
    containment_by_end2 = {
        rel["end2Id"]: rel
        for rel in relations if rel.get("type") == "containment" and rel.get("end2Id")
    }
    cis_by_id = {ci.get("ucmdbId"): ci for ci in cis if ci.get("ucmdbId")}
    
    # Enriquecer inconsistencias
    relaciones_enriquecidas_normales = enriquecer_inconsistencias_normales(
        inconsistencias_normales,
        relations,
        containment_by_end2,
        cis_by_id
    )
    
    relaciones_enriquecidas_particulares = enriquecer_inconsistencias_particulares(
        inconsistencias_particulares,
        relations,
        containment_by_end2,
        cis_by_id
    )
    
    # Guardar reportes
    logger.info("Guardando reportes...")
    guardar_inconsistencias_detalle(relaciones_enriquecidas_normales, carpeta, "inconsistencias.txt")
    guardar_inconsistencias_detalle(relaciones_enriquecidas_particulares, carpeta, "inconsistencias_particulares.txt")
    
    # PASO 6: Eliminaciones
    logger.info("\n")
    eliminar_en_ucmdb(
        token,
        relaciones_enriquecidas_normales,
        carpeta,
        modo_ejecucion=ExecutionFlags.MODO_EJECUCION,
        generar_resumen=ExecutionFlags.GENERAR_RESUMEN
    )
    
    # Filtrar y procesar ITSM (solo con relacion_fo: true)
    logger.info("\n")
    normales_con_fo = [
        item for item in relaciones_enriquecidas_normales
        if item.get("relacion_fo") and item.get("ucmdbid_fo") != "N/A"
    ]
    eliminar_en_itsm(
        normales_con_fo,
        carpeta,
        modo_ejecucion=ExecutionFlags.MODO_EJECUCION,
        generar_resumen=ExecutionFlags.GENERAR_RESUMEN
    )
    
    return ExitCodes.SUCCESS


def main() -> int:
    """
    Función principal del script.
    
    Orquesta todo el proceso de validación y eliminación.
    
    Returns:
        Código de salida (0 = éxito, otro = error)
    """
    logger.info("=" * 80)
    logger.info("VALIDACIÓN DE CONSISTENCIA DE NITs EN UCMDB E ITSM")
    logger.info("=" * 80)
    logger.info(f"Modo: {ExecutionFlags.MODO_EJECUCION.upper()}")
    logger.info("")
    
    # Validación de configuración
    try:
        validar_configuracion_inicial()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        return ExitCodes.CONFIG_ERROR
    
    if ExecutionFlags.MODO_EJECUCION == "ejecucion":
        logger.warning("⚠️  MODO EJECUCIÓN REAL - Se realizarán cambios en los sistemas")
    else:
        logger.info("ℹ️  MODO SIMULACIÓN - No se realizarán cambios reales")
    
    logger.info("")
    
    # PASO 1: Autenticación
    logger.info("PASO 1: AUTENTICACIÓN UCMDB")
    logger.info("-" * 80)
    
    token = None
    
    if not ExecutionFlags.USAR_REPORTE_LOCAL or ExecutionFlags.MODO_EJECUCION == "ejecucion":
        logger.info("Obteniendo token de autenticación...")
        token = obtener_token_ucmdb()
        
        if not token:
            logger.error("Falló autenticación con UCMDB")
            return ExitCodes.AUTH_ERROR
        
        logger.info("✓ Token obtenido exitosamente")
    else:
        logger.info("Token no requerido (modo simulación con reporte local)")
    
    logger.info("")
    
    # PASO 2: Obtener reporte
    logger.info("PASO 2: OBTENER REPORTE")
    logger.info("-" * 80)
    
    reporte_contenido = None
    
    if ExecutionFlags.USAR_REPORTE_LOCAL:
        logger.info(f"Cargando reporte local desde: {ReportConfig.RUTA_REPORTE_LOCAL}")
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
    
    logger.info("")
    
    # PASO 3: Procesar JSON
    logger.info("PASO 3: PROCESAR JSON")
    logger.info("-" * 80)
    
    try:
        json_data = json.loads(reporte_contenido)
    except json.JSONDecodeError as e:
        logger.error(f"Error al decodificar JSON: {e}")
        logger.error(f"  Posición: línea {e.lineno}, columna {e.colno}")
        logger.error(f"  Contexto: {e.doc[max(0, e.pos-50):e.pos+50]}")
        
        if isinstance(reporte_contenido, str):
            tamanio_mb = len(reporte_contenido) / (1024 * 1024)
            logger.error(f"  Tamaño del contenido: {tamanio_mb:.2f} MB")
            
            if tamanio_mb > 100:
                logger.error("\n⚠️  El JSON MUY GRANDE puede estar truncado:")
                logger.error("  1. Verificar si la descarga fue interrumpida")
                logger.error("  2. Si fue truncado, intentar dividir el reporte en partes")
                logger.error("  3. Contactar equipo de UCMDB si el problema persiste")
        
        return ExitCodes.JSON_ERROR
    
    logger.info("✓ JSON procesado exitosamente\n")
    
    # Validar integridad de datos
    if not validar_integridad_json(json_data):
        logger.error("Validación de integridad falló")
        return ExitCodes.JSON_ERROR
    
    # PASO 4: Crear carpeta
    logger.info("PASO 4: CREAR DIRECTORIO DE EJECUCIÓN")
    logger.info("-" * 80)
    
    carpeta_ejecucion = crear_directorio_ejecucion(ExecutionFlags.CREAR_CARPETA_EJECUCION)
    
    if ExecutionFlags.GENERAR_RESUMEN:
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
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\nEjecución cancelada por el usuario")
        sys.exit(ExitCodes.EXECUTION_ERROR)
    except Exception as e:
        logger.exception(f"Error crítico no manejado: {e}")
        sys.exit(ExitCodes.EXECUTION_ERROR)
