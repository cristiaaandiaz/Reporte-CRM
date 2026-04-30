"""
Procesamiento de datos y generación de reportes.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json

from .logger_config import obtener_logger

logger = obtener_logger(__name__)

TIPOS_FO_VALIDOS: List[str] = [
    "clr_service_catalog_fo_e",
    "clr_service_catalog_fo_n",
    "clr_service_catalog_fo_p",
    "clr_service_catalog_fo_cloud"
]

SEPARADOR_REPORTE = "=" * 80
INDENT_JSON = 2


def guardar_reporte_json(json_data: Dict[str, Any], carpeta: Path) -> Optional[Path]:
    """Guarda el JSON completo del reporte."""
    if carpeta.name == "disabled":
        return None
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archivo_reporte = carpeta / f"reporte_{timestamp}.json"
    
    try:
        with open(archivo_reporte, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=INDENT_JSON, ensure_ascii=False)
        logger.info(f"Reporte JSON guardado: {archivo_reporte}")
        return archivo_reporte
    except (IOError, OSError) as e:
        logger.error(f"Error al guardar reporte JSON: {e}")
        return None


def guardar_inconsistencias_detalle(
    inconsistencias: List[Dict[str, Any]],
    carpeta: Path,
    nombre_archivo: str
) -> Optional[Path]:
    """Guarda detalle de inconsistencias encontradas."""
    if not inconsistencias:
        return None
    
    if carpeta.name == "disabled":
        return None
    
    archivo = carpeta / nombre_archivo
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            titulo = nombre_archivo.upper().replace('.TXT', '').replace('_', ' ')
            f.write(SEPARADOR_REPORTE + "\n")
            f.write(titulo.center(80) + "\n")
            f.write(SEPARADOR_REPORTE + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total: {len(inconsistencias)}\n")
            f.write(SEPARADOR_REPORTE + "\n\n")
            
            for idx, item in enumerate(inconsistencias, 1):
                f.write(f"[{idx:04d}] RELACION\n")
                f.write("-" * 80 + "\n")
                f.write(f"  ID Relacion:           {item.get('ucmdbId', 'N/A')}\n")
                f.write(f"  EXTREMO 1 (END1):\n")
                f.write(f"    ID:                  {item.get('end1Id', 'N/A')}\n")
                f.write(f"    Nombre:              {item.get('display_label_end1', 'N/A')}\n")
                f.write(f"    NIT:                 {item.get('nit_end1', 'N/A')}\n")
                f.write(f"  EXTREMO 2 (END2):\n")
                f.write(f"    ID:                  {item.get('end2Id', 'N/A')}\n")
                f.write(f"    Nombre:              {item.get('display_label_end2', 'N/A')}\n")
                f.write(f"    NIT:                 {item.get('nit_end2', 'N/A')}\n")
                f.write(f"  Contiene FO:           {item.get('relacion_fo', 'N/A')}\n")
                f.write(f"  ID FO:                {item.get('ucmdbid_fo', 'N/A')}\n")
                f.write("\n")
        
        logger.info(f"Guardadas {len(inconsistencias)} inconsistencias en: {archivo}")
        return archivo
    except (IOError, OSError) as e:
        logger.error(f"Error guardando {nombre_archivo}: {e}")
        return None


def enriquecer_inconsistencias_normales(
    inconsistencias: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    containment_by_end2: Dict[str, Dict[str, Any]],
    cis_by_id: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Enriquece inconsistencias identificando relaciones Foreign Object (FO)."""
    relations_by_id = {rel.get("ucmdbId"): rel for rel in relations if rel.get("ucmdbId")}
    
    relaciones_enriquecidas: List[Dict[str, Any]] = []
    relaciones_fo_encontradas = 0
    
    for item in inconsistencias:
        ucmdbid = item.get("ucmdbId")
        
        rel_original = relations_by_id.get(ucmdbid)
        if not rel_original:
            relaciones_enriquecidas.append(item)
            continue
        
        end2id = rel_original.get("end2Id")
        
        relacion_fo = False
        ucmdbid_fo = "N/A"
        
        containment_rel = containment_by_end2.get(end2id)
        if containment_rel:
            sc_end1id = containment_rel.get("end1Id")
            ci_node = cis_by_id.get(sc_end1id)
            
            if ci_node and ci_node.get("type") in TIPOS_FO_VALIDOS:
                relacion_fo = True
                ucmdbid_fo = containment_rel.get("ucmdbId", "N/A")
                relaciones_fo_encontradas += 1
        
        item_enriquecido = item.copy()
        item_enriquecido["relacion_fo"] = relacion_fo
        item_enriquecido["ucmdbid_fo"] = ucmdbid_fo
        
        relaciones_enriquecidas.append(item_enriquecido)
    
    logger.debug(f"Enriquecidas {len(relaciones_enriquecidas)} ({relaciones_fo_encontradas} FO)")
    return relaciones_enriquecidas


def crear_directorio_ejecucion(crear_carpeta: bool = True) -> Path:
    """Crea directorio de ejecución con timestamp."""
    reports_dir = Path("reports").resolve()
    
    if not crear_carpeta:
        logger.info("Creación de carpeta deshabilitada")
        return reports_dir / "disabled"
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = reports_dir / f"ejecucion_{timestamp}"
    
    try:
        carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio creado: {carpeta_ejecucion}")
        return carpeta_ejecucion
    except OSError as e:
        logger.error(f"Error creando carpeta: {e}")
        return reports_dir / "disabled"


def validar_integridad_json(json_data: Dict[str, Any]) -> bool:
    """Valida la estructura del JSON descargado de UCMDB."""
    logger.info("=" * 60)
    logger.info("Validando integridad JSON...")
    logger.info("=" * 60)
    
    if not isinstance(json_data, dict):
        logger.error(f"JSON raíz debe ser diccionario, obtenido: {type(json_data).__name__}")
        return False
    
    cis = json_data.get("cis")
    relations = json_data.get("relations")
    
    if cis is None or relations is None:
        logger.error("Campos 'cis' o 'relations' no encontrados")
        return False
    
    if not isinstance(cis, list) or not isinstance(relations, list):
        logger.error("'cis' y 'relations' deben ser listas")
        return False
    
    if not cis or not relations:
        logger.error("Listas vacías")
        return False
    
    logger.info(f"Validación exitosa: {len(cis):,} CIs, {len(relations):,} relaciones")
    return True


def guardar_relaciones_usage_detalle(
    relaciones_usage: List[Dict[str, Any]],
    carpeta: Path,
    nombre_archivo: str = "relaciones_usage_de_servicecodes.txt"
) -> Optional[Path]:
    """Guarda detalle de relaciones usage."""
    if not relaciones_usage:
        return None
    
    if carpeta.name == "disabled":
        return None
    
    archivo = carpeta / nombre_archivo
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            titulo = nombre_archivo.upper().replace('.TXT', '').replace('_', ' ')
            f.write(SEPARADOR_REPORTE + "\n")
            f.write(titulo.center(80) + "\n")
            f.write(SEPARADOR_REPORTE + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total: {len(relaciones_usage)}\n")
            f.write(f"Tipo: usage (App -> Servicecode)\n")
            f.write(SEPARADOR_REPORTE + "\n\n")
            
            for idx, item in enumerate(relaciones_usage, 1):
                f.write(f"[{idx:04d}] RELACION {item.get('type', 'N/A').upper()}\n")
                f.write("-" * 80 + "\n")
                f.write(f"  ID Relacion:           {item.get('ucmdbId', 'N/A')}\n")
                f.write(f"  ORIGEN (END1):\n")
                f.write(f"    ID:                  {item.get('end1Id', 'N/A')}\n")
                f.write(f"    Nombre:              {item.get('display_label_end1', 'N/A')}\n")
                f.write(f"    Tipo:                {item.get('ci_type_end1', 'N/A')}\n")
                f.write(f"  DESTINO (END2):\n")
                f.write(f"    ID:                  {item.get('end2Id', 'N/A')}\n")
                f.write(f"    Nombre:              {item.get('display_label_end2', 'N/A')}\n")
                f.write(f"    Tipo:                {item.get('ci_type_end2', 'N/A')}\n")
                f.write("\n")
        
        logger.info(f"Guardadas {len(relaciones_usage)} relaciones usage en: {archivo}")
        return archivo
    except (IOError, OSError) as e:
        logger.error(f"Error guardando: {e}")
        return None