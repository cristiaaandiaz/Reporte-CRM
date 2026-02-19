"""
Módulo de Procesamiento de Datos.

Gestiona el enriquecimiento y procesamiento de datos de inconsistencias.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json

from .logger_config import obtener_logger

logger = obtener_logger(__name__)

# Tipos de CI que se consideran "Foreign Object" válidos
TIPOS_FO_VALIDOS = [
    "clr_service_catalog_fo_e",
    "clr_service_catalog_fo_n",
    "clr_service_catalog_fo_p",
    "clr_service_catalog_fo_cloud"
]

# Configuración de output
SEPARADOR_REPORTE = "=" * 80
INDENT_JSON = 2


def guardar_reporte_json(
    json_data: Dict[str, Any],
    carpeta: Path
) -> Optional[Path]:
    """
    Guarda el JSON completo del reporte.
    
    Args:
        json_data: Datos JSON a guardar (esperado con claves 'cis' y 'relations')
        carpeta: Carpeta donde guardar (si es 'disabled', omite guardado)
    
    Returns:
        Ruta del archivo guardado o None si está deshabilitado o error
        
    Ejemplo:
        >>> ruta = guardar_reporte_json({"cis": [...], "relations": [...]}, Path("reports"))
        >>> print(ruta)  # reports/reporte_2026-02-19_08-30-00.json
    """
    if carpeta.name == "disabled":
        logger.debug("Guardado de reporte JSON deshabilitado")
        return None
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archivo_reporte = carpeta / f"reporte_{timestamp}.json"
    
    try:
        with open(archivo_reporte, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=INDENT_JSON, ensure_ascii=False)
        logger.info(f"Reporte JSON guardado: {archivo_reporte}")
        return archivo_reporte
    except (IOError, OSError) as e:
        logger.error(f"Error al guardar reporte JSON en {archivo_reporte}: {e}")
        return None


def guardar_inconsistencias_detalle(
    inconsistencias: List[Dict[str, Any]],
    carpeta: Path,
    nombre_archivo: str
) -> Optional[Path]:
    """
    Guarda detalle de inconsistencias encontradas en formato texto.
    
    Genera un archivo con una inconsistencia por entrada, mostrando:
    - IDs de relación, end1 y end2
    - Nombres de CIs (display labels)
    - NITs de ambos extremos
    - Estado FO (Foreign Object) si aplica
    
    Args:
        inconsistencias: Lista de inconsistencias con estructura {ucmdbId, end1Id, end2Id, ...}
        carpeta: Carpeta destino (si es 'disabled', omite guardado)
        nombre_archivo: Nombre del archivo output (ej: 'inconsistencias.txt')
    
    Returns:
        Ruta del archivo guardado o None si está vacío/deshabilitado
    """
    if not inconsistencias:
        logger.debug(f"Sin inconsistencias para guardar en {nombre_archivo}")
        return None

    if carpeta.name == "disabled":
        logger.debug(f"Guardado de {nombre_archivo} deshabilitado")
        return None

    archivo = carpeta / nombre_archivo

    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(SEPARADOR_REPORTE + "\n")
            f.write(f"{nombre_archivo.upper().replace('.TXT', '').replace('_', ' ')}\n")
            f.write(SEPARADOR_REPORTE + "\n\n")
            
            for idx, item in enumerate(inconsistencias, 1):
                # Extraer campos con valores por defecto
                relation_id = item.get("ucmdbId", "N/A")
                end1_id = item.get("end1Id", "N/A")
                end2_id = item.get("end2Id", "N/A")
                end1_label = item.get("display_label_end1", "N/A")
                end2_label = item.get("display_label_end2", "N/A")
                nit_end1 = item.get("nit_end1", "N/A")
                nit_end2 = item.get("nit_end2", "N/A")
                relacion_fo = item.get("relacion_fo", "N/A")
                id_fo = item.get("ucmdbid_fo", "N/A")
                
                f.write(f"[{idx}] ID Relación: {relation_id}\n")
                f.write(f"    End1 ID: {end1_id}\n")
                f.write(f"    End2 ID: {end2_id}\n")
                f.write(f"    End1 Label: {end1_label}\n")
                f.write(f"    End2 Label: {end2_label}\n")
                f.write(f"    NIT End1: {nit_end1}\n")
                f.write(f"    NIT End2: {nit_end2}\n")
                f.write(f"    Relación FO: {relacion_fo}\n")
                f.write(f"    ID FO: {id_fo}\n")
                f.write("\n")

        logger.info(f"Guardadas {len(inconsistencias)} inconsistencias en: {archivo}")
        return archivo
    except (IOError, OSError) as e:
        logger.error(f"Error guardando {nombre_archivo} en {archivo}: {e}")
        return None


def enriquecer_inconsistencias_normales(
    inconsistencias: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    containment_by_end2: Dict[str, Dict[str, Any]],
    cis_by_id: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Enriquece inconsistencias normales identificando relaciones "Foreign Object" (FO).
    
    Algoritmo:
    Para cada inconsistencia:
    1. Obtiene el end2Id de la relación original
    2. Busca si existe una relación CONTAINMENT con ese end2Id
    3. Verifica si el CI[end1Id] de containment es de tipo FO válido
    4. Si es FO: marca relacion_fo=True y guarda ucmdbId_fo para rastreo
    
    Tipos FO válidos: {', '.join(TIPOS_FO_VALIDOS)}
    
    Args:
        inconsistencias: Lista de inconsistencias normales (NIT end1 ≠ NIT end2)
        relations: Lista de todas las relaciones, indexadas por ucmdbId
        containment_by_end2: Dict pre-indexado {end2Id -> relación_containment}
        cis_by_id: Dict pre-indexado {ucmdbId -> CI_node}
    
    Returns:
        Lista enriquecida con campos 'relacion_fo' (bool) y 'ucmdbid_fo' (str)
        
    Nota:
        Si la relación original no se encuentra, la inconsistencia se devuelve sin enriquecer
    """
    # Pre-indexar relaciones por ucmdbId para búsqueda O(1)
    relations_by_id = {rel.get("ucmdbId"): rel for rel in relations if rel.get("ucmdbId")}
    logger.debug(f"Indexadas {len(relations_by_id)} relaciones para enriquecimiento")
    
    relaciones_enriquecidas = []
    relaciones_fo_encontradas = 0
    relaciones_sin_enriquecer = 0
    
    for item in inconsistencias:
        ucmdbid = item.get("ucmdbId")
        
        # Obtener la relación original para extraer end2Id
        rel_original = relations_by_id.get(ucmdbid)
        if not rel_original:
            logger.warning(f"Relación original no indexada: {ucmdbid}")
            relaciones_sin_enriquecer += 1
            relaciones_enriquecidas.append(item)
            continue
        
        end2id = rel_original.get("end2Id")
        
        # Buscar relación FO (CONTAINMENT)
        relacion_fo = False
        ucmdbid_fo = "N/A"
        
        containment_rel = containment_by_end2.get(end2id)
        if containment_rel:
            # Verificar si el CI en end1Id de containment es tipo FO válido
            sc_end1id = containment_rel.get("end1Id")
            ci_node = cis_by_id.get(sc_end1id)
            
            if ci_node and ci_node.get("type") in TIPOS_FO_VALIDOS:
                relacion_fo = True
                ucmdbid_fo = containment_rel.get("ucmdbId", "N/A")
                relaciones_fo_encontradas += 1
        
        # Agregar información enriquecida
        item_enriquecido = item.copy()
        item_enriquecido["relacion_fo"] = relacion_fo
        item_enriquecido["ucmdbid_fo"] = ucmdbid_fo
        
        relaciones_enriquecidas.append(item_enriquecido)
    
    logger.debug(f"Enriquecidas {len(relaciones_enriquecidas)} inconsistencias normales"
                f" ({relaciones_fo_encontradas} FO encontradas)")
    if relaciones_sin_enriquecer > 0:
        logger.warning(f"No se pudieron enriquecer {relaciones_sin_enriquecer} relaciones")
    
    return relaciones_enriquecidas


def enriquecer_inconsistencias_particulares(
    inconsistencias: List[Dict[str, Any]],
    containment_by_end2: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Enriquece inconsistencias particulares con información de contención.
    
    Algoritmo:
    1. Para cada inconsistencia particular, obtiene end2Id
    2. Busca en containment_by_end2 para extraer end1Id_containment
    3. Si no encuentra la información, asigna "N/A"
    4. Retorna lista de inconsistencias con campo end1Id_containment añadido
    
    Args:
        inconsistencias: Lista de inconsistencias particulares a enriquecer
        containment_by_end2: Índice de relaciones de contención (clave: end2Id)
    
    Returns:
        Lista de inconsistencias enriquecidas con información de contención
        
    Ejemplo:
        >>> inconsistencias = [{"end2Id": "ci123", "reltype": "ITSM"}]
        >>> containment = {"ci123": {"end1Id": "container456"}}
        >>> resultado = enriquecer_inconsistencias_particulares(inconsistencias, containment)
        >>> resultado[0]["end1Id_containment"]  # "container456"
    """
    if not inconsistencias:
        logger.debug("No hay inconsistencias particulares para enriquecer")
        return []
    
    relaciones_enriquecidas = []
    enriquecidas_exitosas = 0
    no_encontradas = 0
    
    for item in inconsistencias:
        end2id = item.get("end2Id")
        
        if not end2id:
            logger.warning(f"Item sin end2Id: {item}")
            item["end1Id_containment"] = "N/A"
            no_encontradas += 1
        elif end2id in containment_by_end2:
            containment_rel = containment_by_end2[end2id]
            item["end1Id_containment"] = containment_rel.get("end1Id", "N/A")
            enriquecidas_exitosas += 1
        else:
            item["end1Id_containment"] = "N/A"
            no_encontradas += 1
        
        relaciones_enriquecidas.append(item.copy())
    
    logger.info(f"Enriquecidas {enriquecidas_exitosas}/{len(relaciones_enriquecidas)} "
                f"inconsistencias particulares (no encontradas: {no_encontradas})")
    
    return relaciones_enriquecidas


def crear_directorio_ejecucion(crear_carpeta: bool = True) -> Path:
    """
    Crea directorio de ejecución con timestamp o retorna path 'disabled'.
    
    Cuando crear_carpeta=True:
    - Crea directorio: reports/ejecucion_YYYY-MM-DD_HH-MM-SS/
    - Retorna Path al directorio creado
    
    Cuando crear_carpeta=False:
    - Retorna Path a 'reports/disabled' (sin crear)
    - Útil para deshabilitar guardado de archivos
    
    Args:
        crear_carpeta: Si True, crea carpeta con timestamp; si False, retorna 'disabled'
    
    Returns:
        Path del directorio nuevo o Path a 'disabled'
        
    Ejemplo:
        >>> carpeta = crear_directorio_ejecucion(True)
        >>> print(carpeta)  # reports/ejecucion_2026-02-19_08-30-00
    """
    reports_dir = Path("reports").resolve()
    
    if not crear_carpeta:
        logger.info("Creación de carpeta de ejecución deshabilitada")
        return reports_dir / "disabled"
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = reports_dir / f"ejecucion_{timestamp}"
    
    try:
        carpeta_ejecucion.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio de ejecución creado: {carpeta_ejecucion}")
        return carpeta_ejecucion
    except OSError as e:
        logger.error(f"Error creando carpeta {carpeta_ejecucion}: {e}")
        # Fallback: retornar disabled
        return reports_dir / "disabled"


def validar_integridad_json(json_data: Dict[str, Any]) -> bool:
    """
    Valida la integridad y estructura del JSON descargado de UCMDB.
    
    Algoritmo de validación en cascada:
    1. Verifica que JSON raíz sea diccionario
    2. Verifica existencia de claves principales ('cis', 'relations')
    3. Verifica que ambas sean listas no vacías
    4. Verifica estructura de elementos individuales (ucmdbId, end1Id, end2Id)
    5. Verifica completitud del último elemento (detección de truncado)
    
    Verifica:
    ✓ JSON raíz es diccionario
    ✓ Claves 'cis' y 'relations' existen y son listas
    ✓ Ambas listas tienen al menos 1 elemento
    ✓ Elementos mínimos tienen estructura esperada (ucmdbId, type, etc.)
    ✓ Último elemento no está truncado
    
    Args:
        json_data: Diccionario JSON a validar desde UCMDB
    
    Returns:
        True si JSON es válido y completo, False si hay errores
        
    Ejemplo:
        >>> datos = {"cis": [{"ucmdbId": "ci1"}], "relations": [{"ucmdbId": "rel1"}]}
        >>> es_valido = validar_integridad_json(datos)  # True
    """
    logger.info("=" * 60)
    logger.info("Iniciando validación de integridad JSON...")
    logger.info("=" * 60)
    
    # Validar tipo raíz
    if not isinstance(json_data, dict):
        logger.error(f"❌ JSON raíz debe ser diccionario, obtenido: {type(json_data).__name__}")
        return False
    
    logger.debug("✓ JSON raíz es diccionario")
    
    # Validar claves principales
    cis = json_data.get("cis")
    relations = json_data.get("relations")
    
    if cis is None:
        logger.error("❌ Campo 'cis' no encontrado en JSON")
        return False
    
    logger.debug("✓ Campo 'cis' encontrado")
    
    if relations is None:
        logger.error("❌ Campo 'relations' no encontrado en JSON")
        return False
    
    logger.debug("✓ Campo 'relations' encontrado")
    
    # Validar que sean listas
    if not isinstance(cis, list):
        logger.error(f"❌ Campo 'cis' debe ser lista, obtenido: {type(cis).__name__}")
        return False
    
    if not isinstance(relations, list):
        logger.error(f"❌ Campo 'relations' debe ser lista, obtenido: {type(relations).__name__}")
        return False
    
    logger.debug("✓ Tanto 'cis' como 'relations' son listas")
    
    # Validar que no estén vacías
    if len(cis) == 0:
        logger.error("❌ No hay CIs en el JSON (lista vacía)")
        return False
    
    if len(relations) == 0:
        logger.error("❌ No hay relaciones en el JSON (lista vacía)")
        return False
    
    logger.debug(f"✓ Listas no vacías: {len(cis)} CIs, {len(relations)} relaciones")
    
    # Validar estructura de elementos principales
    try:
        # Verificar estructura de primer CI
        primer_ci = cis[0]
        if not isinstance(primer_ci, dict):
            logger.warning(f"⚠ Primer CI no es diccionario: {type(primer_ci).__name__}")
        elif "ucmdbId" not in primer_ci:
            logger.warning("⚠ Primer CI no tiene campo 'ucmdbId'")
        else:
            logger.debug(f"✓ Primer CI válido: {primer_ci.get('ucmdbId', 'N/A')}")
        
        # Verificar estructura de primera relación
        primera_rel = relations[0]
        if not isinstance(primera_rel, dict):
            logger.warning(f"⚠ Primera relación no es diccionario: {type(primera_rel).__name__}")
        elif "ucmdbId" not in primera_rel:
            logger.warning("⚠ Primera relación no tiene campo 'ucmdbId'")
        else:
            logger.debug(f"✓ Primera relación válida: {primera_rel.get('ucmdbId', 'N/A')}")
        
        # Verificar que el último elemento de relaciones está completo
        ultima_rel = relations[-1]
        if not isinstance(ultima_rel, dict):
            logger.error(f"❌ Última relación no es diccionario: {type(ultima_rel).__name__}")
            return False
        
        if "ucmdbId" not in ultima_rel:
            logger.error("❌ Última relación no tiene campo 'ucmdbId' (posiblemente truncada)")
            return False
        
        if "end1Id" not in ultima_rel or "end2Id" not in ultima_rel:
            logger.error("❌ Última relación está faltando campos clave (end1Id, end2Id)")
            return False
        
        logger.debug(f"✓ Última relación completa: {ultima_rel.get('ucmdbId', 'N/A')}")
        
    except (IndexError, KeyError, TypeError) as e:
        logger.error(f"❌ Error validando estructura: {type(e).__name__}: {e}")
        return False
    
    logger.info("=" * 60)
    logger.info(f"✅ Validación exitosa: {len(cis):,} CIs, {len(relations):,} relaciones")
    logger.info("=" * 60)
    return True
