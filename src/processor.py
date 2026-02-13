"""
Módulo de Procesamiento de Datos.

Gestiona el enriquecimiento y procesamiento de datos de inconsistencias.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from .logger_config import obtener_logger

logger = obtener_logger(__name__)


def guardar_reporte_json(
    json_data: Dict[str, Any],
    carpeta: Path
) -> Optional[Path]:
    """
    Guarda el JSON completo del reporte.
    
    Args:
        json_data: Datos JSON a guardar
        carpeta: Carpeta donde guardar
    
    Returns:
        Ruta del archivo guardado o None si está deshabilitado
    """
    if carpeta.name == "disabled":
        logger.info("Guardado de reporte JSON deshabilitado")
        return None
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archivo_reporte = carpeta / f"reporte_{timestamp}.json"
    
    try:
        with open(archivo_reporte, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
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
    """
    Guarda detalle de inconsistencias encontradas.
    
    Args:
        inconsistencias: Lista de inconsistencias
        carpeta: Carpeta donde guardar
        nombre_archivo: Nombre del archivo
    
    Returns:
        Ruta del archivo guardado o None
    """
    if not inconsistencias:
        logger.info(f"Sin inconsistencias para {nombre_archivo}")
        return None

    if carpeta.name == "disabled":
        logger.info(f"Guardado de {nombre_archivo} deshabilitado")
        return None

    archivo = carpeta / nombre_archivo

    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"{nombre_archivo.upper().replace('_', ' ')}\n")
            f.write("=" * 80 + "\n\n")
            
            for idx, item in enumerate(inconsistencias, 1):
                f.write(f"[{idx}] ID Relación: {item.get('ucmdbId', 'N/A')}\n")
                f.write(f"    End1 ID: {item.get('end1Id', 'N/A')}\n")
                f.write(f"    End2 ID: {item.get('end2Id', 'N/A')}\n")
                f.write(f"    End1 Label: {item.get('display_label_end1', 'N/A')}\n")
                f.write(f"    End2 Label: {item.get('display_label_end2', 'N/A')}\n")
                f.write(f"    NIT End1: {item.get('nit_end1', 'N/A')}\n")
                f.write(f"    NIT End2: {item.get('nit_end2', 'N/A')}\n")
                f.write(f"    Relación FO: {item.get('relacion_fo', 'N/A')}\n")
                f.write(f"    ID FO: {item.get('ucmdbid_fo', 'N/A')}\n")
                f.write("\n")

        logger.info(f"Inconsistencias guardadas: {archivo}")
        return archivo
    except IOError as e:
        logger.error(f"Error guardando {nombre_archivo}: {e}")
        return None


def enriquecer_inconsistencias_normales(
    inconsistencias: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    containment_by_end2: Dict[str, Dict[str, Any]],
    cis_by_id: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Enriquece inconsistencias normales con información de relación_fo y ucmdbid_fo.
    
    Busca relaciones "foreign object" (FO):
    1. Para cada inconsistencia, obtiene su end2Id
    2. Busca si existe una relación de CONTAINMENT con ese end2Id
    3. Si existe, verifica si el CI en end1Id es de tipo "clr_service_catalog_fo_e"
    4. Si es FO, marca relacion_fo=True y guarda el ucmdbId de la relación containment
    
    Args:
        inconsistencias: Lista de inconsistencias normales
        relations: Lista de todas las relaciones
        containment_by_end2: Índice de relaciones de contención by end2Id
        cis_by_id: Índice de CIs por ID
    
    Returns:
        Lista de inconsistencias enriquecidas
    """
    relations_by_id = {rel.get("ucmdbId"): rel for rel in relations if rel.get("ucmdbId")}
    relaciones_enriquecidas = []
    
    for item in inconsistencias:
        ucmdbid = item.get("ucmdbId")
        
        # Obtener la relación original para extraer end1Id y end2Id
        rel_original = relations_by_id.get(ucmdbid)
        if not rel_original:
            # No enriquecer si no encontramos la relación original
            relaciones_enriquecidas.append(item)
            continue
        
        end1id = rel_original.get("end1Id")
        end2id = rel_original.get("end2Id")
        
        # Búsqueda de relación FO:
        # 1. Buscar relación de CONTAINMENT con ese end2Id
        relacion_fo = False
        ucmdbid_fo = "N/A"
        
        containment_rel = containment_by_end2.get(end2id)
        if containment_rel:
            # 2. Verificar si el CI en end1Id es de uno de los tipos FO válidos
            sc_end1id = containment_rel.get("end1Id")
            ci_node = cis_by_id.get(sc_end1id)
            tipos_fo_validos = [
                "clr_service_catalog_fo_e",
                "clr_service_catalog_fo_n",
                "clr_service_catalog_fo_p",
                "clr_service_catalog_fo_cloud"
            ]
            if ci_node and ci_node.get("type") in tipos_fo_validos:
                # 3. Si es FO, marcar como tal y guardar el ucmdbId de la relación containment
                relacion_fo = True
                ucmdbid_fo = containment_rel.get("ucmdbId", "N/A")
        
        # Agregar información enriquecida
        item_enriquecido = item.copy()
        item_enriquecido["relacion_fo"] = relacion_fo
        item_enriquecido["ucmdbid_fo"] = ucmdbid_fo
        
        relaciones_enriquecidas.append(item_enriquecido)
    
    logger.debug(f"Enriquecidas {len(relaciones_enriquecidas)} inconsistencias normales")
    return relaciones_enriquecidas


def enriquecer_inconsistencias_particulares(
    inconsistencias: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    containment_by_end2: Dict[str, Dict[str, Any]],
    cis_by_id: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Enriquece inconsistencias particulares con información adicional.
    
    Args:
        inconsistencias: Lista de inconsistencias particulares
        relations: Lista de todas las relaciones
        containment_by_end2: Índice de relaciones de contención
        cis_by_id: Índice de CIs por ID
    
    Returns:
        Lista de inconsistencias enriquecidas
    """
    relaciones_enriquecidas = []
    
    for item in inconsistencias:
        # Buscar información de containment
        end2id = item.get("end2Id")
        if end2id in containment_by_end2:
            containment_rel = containment_by_end2[end2id]
            item["end1Id_containment"] = containment_rel.get("end1Id", "N/A")
        else:
            item["end1Id_containment"] = "N/A"
        
        item_enriquecido = item.copy()
        relaciones_enriquecidas.append(item_enriquecido)
    
    logger.debug(f"Enriquecidas {len(relaciones_enriquecidas)} inconsistencias particulares")
    return relaciones_enriquecidas


def crear_directorio_ejecucion(crear_carpeta: bool = True) -> Path:
    """
    Crea directorio de ejecución con timestamp.
    
    Args:
        crear_carpeta: Si True, crea carpeta; si False, retorna Path 'disabled'
    
    Returns:
        Path del directorio creado o Path a 'disabled'
    """
    from pathlib import Path
    from datetime import datetime
    
    reports_dir = Path("reports")
    
    if not crear_carpeta:
        logger.info("Creación de carpeta de ejecución deshabilitada")
        return reports_dir / "disabled"
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = reports_dir / f"ejecucion_{timestamp}"
    carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
    return carpeta_ejecucion


def validar_integridad_json(json_data: Dict[str, Any]) -> bool:
    """
    Valida la integridad del JSON descargado.
    
    Returns:
        bool: True si los datos se ven válidos
    """
    logger.info("Validando integridad de datos JSON...")
    
    if not isinstance(json_data, dict):
        logger.error("El JSON raíz no es un diccionario")
        return False
    
    cis = json_data.get("cis", [])
    relations = json_data.get("relations", [])
    
    if not isinstance(cis, list):
        logger.error("El campo 'cis' no es una lista")
        return False
    
    if not isinstance(relations, list):
        logger.error("El campo 'relations' no es una lista")
        return False
    
    if len(cis) == 0:
        logger.error("No hay CIs en el JSON")
        return False
    
    if len(relations) == 0:
        logger.error("No hay relaciones en el JSON")
        return False
    
    # Verificar que el último elemento de 'relations' está completo
    if relations:
        ultimo = relations[-1]
        if not isinstance(ultimo, dict) or "ucmdbId" not in ultimo:
            logger.warning("El último elemento de relaciones podría estar truncado")
    
    logger.info(f"✓ Validación de integridad: {len(cis)} CIs, {len(relations)} relaciones")
    return True
