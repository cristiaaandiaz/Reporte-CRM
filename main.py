"""
Script principal para la validación de consistencia de NITs en UCMDB.

Este script autentica con UCMDB, obtiene reportes de contratos CRM,
filtra nodos de tipo clr_onyxservicecodes, valida relaciones entre 
nodos y genera reportes de inconsistencias.
"""

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
    validar_nit_en_relaciones_invertidas
)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ucmdb_validation.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Constantes
REPORTS_BASE_DIR = "reports"
REPORTE_FILENAME = "reporte_{timestamp}.json"
INCONSISTENCIAS_FILENAME = "inconsistencias.txt"

# Códigos de salida
EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 1
EXIT_REPORT_ERROR = 2
EXIT_JSON_ERROR = 3


def crear_directorio_ejecucion() -> Path:
    """
    Crea un directorio único para la ejecución actual.

    Returns:
        Path: Ruta del directorio creado con timestamp.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = Path(REPORTS_BASE_DIR) / f"ejecucion_{timestamp}"
    carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
    return carpeta_ejecucion


def guardar_reporte_json(
    json_data: Dict[str, Any], 
    carpeta: Path
) -> Optional[Path]:
    """
    Guarda el reporte JSON completo en un archivo.

    Args:
        json_data (Dict[str, Any]): Datos del reporte en formato JSON.
        carpeta (Path): Directorio donde guardar el archivo.

    Returns:
        Optional[Path]: Ruta del archivo guardado, o None si hubo error.
    """
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


def guardar_inconsistencias(
    inconsistencias: List[str], 
    carpeta: Path
) -> Optional[Path]:
    """
    Guarda las inconsistencias detectadas en un archivo numerado.

    Args:
        inconsistencias (List[str]): Lista de ucmdbId con inconsistencias.
        carpeta (Path): Directorio donde guardar el archivo.

    Returns:
        Optional[Path]: Ruta del archivo guardado, o None si hubo error.
    """
    if not inconsistencias:
        logger.info("No se encontraron inconsistencias. No se generó archivo.")
        return None
    
    archivo_inconsistencias = carpeta / INCONSISTENCIAS_FILENAME
    
    try:
        with open(archivo_inconsistencias, "w", encoding="utf-8") as f:
            # Encabezado con metadatos
            f.write(f"Reporte de Inconsistencias de NITs\n")
            f.write(f"Fecha: {datetime.now().isoformat()}\n")
            f.write(f"Total: {len(inconsistencias)}\n")
            f.write("=" * 50 + "\n\n")
            
            # Lista numerada de inconsistencias
            for i, rel_id in enumerate(inconsistencias, start=1):
                f.write(f"{i}. {rel_id}\n")
        
        logger.info(
            f"Inconsistencias guardadas en: {archivo_inconsistencias}"
        )
        return archivo_inconsistencias
        
    except IOError as e:
        logger.error(f"Error al guardar inconsistencias: {e}")
        return None


def procesar_reporte(json_data: Dict[str, Any], carpeta: Path) -> int:
    """
    Procesa el reporte: filtra, valida y guarda resultados.

    Args:
        json_data (Dict[str, Any]): Datos del reporte JSON.
        carpeta (Path): Directorio donde guardar los resultados.

    Returns:
        int: Código de salida (0 = éxito).
    """
    # Filtrar objetos de tipo servicecodes
    logger.info("Filtrando objetos de tipo 'clr_onyxservicecodes'...")
    cis_filtrados = filtrar_cis_por_tipo_servicecodes(json_data)
    cis_log = extraer_datos_relevantes_servicecodes(cis_filtrados)
    
    logger.info(f"Total de objetos filtrados: {len(cis_log)}")
    
    # Validar NITs en relaciones
    logger.info("Iniciando validación de NITs en relaciones...")
    inconsistencias = validar_nit_en_relaciones_invertidas(json_data)
    
    logger.info(
        f"Relaciones con NIT diferentes encontradas: {len(inconsistencias)}"
    )
    
    # Mostrar inconsistencias en log
    if inconsistencias:
        logger.warning("Se detectaron las siguientes inconsistencias:")
        for rel_id in inconsistencias[:10]:  # Mostrar máximo 10 en consola
            logger.warning(f"  - Relación ucmdbId: {rel_id}")
        
        if len(inconsistencias) > 10:
            logger.warning(
                f"  ... y {len(inconsistencias) - 10} inconsistencias más"
            )
    
    # Guardar inconsistencias en archivo
    guardar_inconsistencias(inconsistencias, carpeta)
    
    return EXIT_SUCCESS


def main() -> int:
    """
    Función principal del script de validación UCMDB.

    Ejecuta el flujo completo:
    1. Autenticación con UCMDB
    2. Obtención del reporte
    3. Procesamiento y validación
    4. Generación de reportes de salida

    Returns:
        int: Código de salida del programa.
    """
    logger.info("=" * 60)
    logger.info("Iniciando validación de consistencia de NITs en UCMDB")
    logger.info("=" * 60)
    
    # Paso 1: Autenticación
    logger.info("Paso 1/4: Autenticando con UCMDB...")
    token = obtener_token_ucmdb()
    
    if not token:
        logger.error("No se pudo obtener el token. Finalizando ejecución.")
        return EXIT_AUTH_ERROR
    
    logger.info("Autenticación exitosa")
    
    # Paso 2: Obtener reporte
    logger.info("Paso 2/4: Consultando reporte de contratos CRM...")
    reporte = consultar_reporte_ucmdb(token)
    
    if not reporte:
        logger.error("No se pudo obtener el reporte. Finalizando ejecución.")
        return EXIT_REPORT_ERROR
    
    logger.info("Reporte obtenido exitosamente")
    
    # Paso 3: Parsear JSON
    logger.info("Paso 3/4: Procesando datos JSON...")
    try:
        json_data = json.loads(reporte)
    except json.JSONDecodeError as e:
        logger.error(f"El contenido del reporte no es un JSON válido: {e}")
        return EXIT_JSON_ERROR
    
    # Crear directorio de salida
    carpeta_ejecucion = crear_directorio_ejecucion()
    
    # Guardar reporte completo
    guardar_reporte_json(json_data, carpeta_ejecucion)
    
    # Paso 4: Procesar y validar
    logger.info("Paso 4/4: Validando datos y generando reportes...")
    exit_code = procesar_reporte(json_data, carpeta_ejecucion)
    
    logger.info("=" * 60)
    logger.info("Procesamiento completado exitosamente")
    logger.info(f"Resultados guardados en: {carpeta_ejecucion}")
    logger.info("=" * 60)
    
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\nEjecución interrumpida por el usuario")
        sys.exit(130)  # Código estándar para SIGINT
    except Exception as e:
        logger.exception(f"Error inesperado durante la ejecución: {e}")
        sys.exit(1)
