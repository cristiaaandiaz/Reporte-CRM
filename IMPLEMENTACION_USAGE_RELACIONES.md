# Implementación: Eliminación de Relaciones Usage de Servicecodes

## Resumen

Se ha implementado una nueva funcionalidad para la detección y eliminación de relaciones tipo `usage` vinculadas a servicecodes (`clr_onyxservicecodes`) que se conectan a aplicaciones (`business_application`).

---

## Cambios Realizados

### 1. **report.py** - Nueva función de validación
**Función:** `validar_relaciones_usage_de_servicecodes()`

**Algoritmo:**
```
1. Filtra CIs de tipo 'clr_onyxservicecodes'
2. Para cada servicecode, busca relaciones donde:
   - end2Id = ucmdbId del servicecode
   - type = 'usage' (case-insensitive)
3. Valida que end1Id sea de tipo 'business_application'
4. Si cumple condiciones, agrega a lista de relaciones a eliminar
5. Si no existe relación, no hace nada (retorna lista_vacía)
```

**Output:**
- Lista de relaciones usage validadas con estructura:
  ```python
  {
      "ucmdbId": "id_relacion",
      "end1Id": "id_business_app",
      "end2Id": "id_servicecode",
      "type": "usage",
      "display_label_end1": "nombre_app",
      "display_label_end2": "nombre_servicecode",
      "ci_type_end1": "business_application",
      "ci_type_end2": "clr_onyxservicecodes"
  }
  ```

**Logs:**
- Total de CIs indexados
- Total de servicecodes encontrados
- Total de relaciones usage indexadas
- Por cada servicecode: estado de validación
- Resumen final con conteos

---

### 2. **processor.py** - Función para guardar reportes
**Función:** `guardar_relaciones_usage_detalle()`

**Propósito:**
- Guardar detalle de relaciones usage en archivo TXT para auditoría
- Generar reporte legible con estructura clara

**Output File:**
`relaciones_usage_de_servicecodes.txt`

**Formato del archivo:**
```
================================================================================
RELACIONES USAGE DE SERVICECODES
================================================================================

[1] ID Relacion: 4e574223f916f853a2f9832b6205e47d
    Tipo Relacion: usage
    End1 (Aplicacion):
      ID: 4d385622719e6d5db31653ae13306eba
      Tipo: business_application
      Nombre: CONECTIVIDAD
    End2 (Servicecode):
      ID: 4700dc2a5c00a4c48d17ea1d072be2ec
      Tipo: clr_onyxservicecodes
      Nombre: AABIXG0134

[2] ...
```

---

### 3. **ucmdb_operations.py** - Funciones de eliminación
**Función 1:** `eliminar_relaciones_usage_de_servicecodes()`

**Propósito:**
- Ejecutar eliminaciones (DELETE) en UCMDB para relaciones usage
- Manejo de modo simulación vs ejecución
- Tratamiento especial para errores 404 (no falla si no existe)

**Características:**
- ✅ Reintentos automáticos con backoff exponencial
- ✅ Logging detallado de cada DELETE
- ✅ Distingue entre errores vs recursos no encontrados (404)
- ✅ Resumen de operaciones

**Función 2:** `_guardar_resumen_usage()`

**Output File:**
`resumen_eliminacion_usage.txt`

**Formato del archivo:**
```
================================================================================
RESUMEN DE ELIMINACIÓN DE RELACIONES USAGE
================================================================================

[1] DELETE 4e574223f916f853a2f9832b6205e47d
  URL: https://UCMDB_SERVER/rest/ci/4e574223f916f853a2f9832b6205e47d
  Tipo relación: usage
  Aplicación: CONECTIVIDAD
  Servicecode: AABIXG0134
  Modo: SIMULACION
  Estado: SIMULADA
  
[2] ...

================================================================================
Resumen:
  Total relaciones procesadas: X
  Exitosas: X
  Fallidas: X
  No encontradas (404): X
================================================================================
```

---

### 4. **main.py** - Integración en el flujo

**Cambios:**
1. Imports actualizados:
   - `validar_relaciones_usage_de_servicecodes` de `report.py`
   - `guardar_relaciones_usage_detalle` de `processor.py`
   - `eliminar_relaciones_usage_de_servicecodes` de `ucmdb_operations.py`

2. Función `procesar_reporte()` actualizada:
   - PASO 5.1: Validar relaciones usage (después de NITs)
   - PASO 6A: Eliminaciones NITs (existente)
   - **PASO 6B (NUEVO)**: Eliminaciones usage de servicecodes
   - PASO 7: Guarda en reporte detallado

**Flujo de ejecución:**
```
1. Validar NITs → inconsistencias_normales, particulares
2. Validar relaciones usage → relaciones_usage_a_eliminar
3. Guardar reportes
4. Eliminar NITs en UCMDB
5. Eliminar relaciones usage en UCMDB ← NUEVO
6. Eliminar en ITSM (solo FO)
```

---

## Archivos de Reporte

Al ejecutar el script, se generarán:

1. **relaciones_usage_de_servicecodes.txt** - Detalle de relaciones validadas
2. **resumen_eliminacion_usage.txt** - Resumen de operaciones (PASO 6B)

Ambos se guardarán en: `reports/ejecucion_YYYY-MM-DD_HH-MM-SS/`

---

## Comportamiento por Modo

### Modo Simulación
```
[SIMULACIÓN] Se mostrarán URLs sin ejecutar
[{idx}/{total}] DELETE - Relación usage: {ucmdbid}
  Tipo: usage
  Aplicación: {label_end1} ({end1id})
  Servicecode: {label_end2} ({end2id})
  [SIM] DELETE {url}
  Estado: SIMULADA
```

### Modo Ejecución
```
[EJECUCIÓN] Se eliminarán relaciones usage REALMENTE en UCMDB
[{idx}/{total}] DELETE - Relación usage: {ucmdbid}
  ...
  ✓ HTTP 204 OK - {ucmdbid}
  Estado: EXITOSA
  
Resumen eliminación usage:
  Total relaciones procesadas: X
  Exitosas: X
  Fallidas: X
  No encontradas (404): X
```

---

## Casos Especiales Manejados

1. **Relación no existe (404):** No falla, se registra como "NO_ENCONTRADA"
2. **CI no existe:** Se rechaza validación sin agregar a lista
3. **end1Id no es business_application:** Se rechaza validación
4. **Lista vacía:** Salta el paso 6B sin error
5. **Modo simulación:** Solo muestra URLs sin hacer DELETE

---

## Ejemplo de Ejecución

Con el JSON de ejemplo proporcionado:

```
CI servicecode: 4700dc2a5c00a4c48d17ea1d072be2ec (AABIXG0134)
  ↓
Relación usage encontrada: 4e574223f916f853a2f9832b6205e47d
  end1Id: 4d385622719e6d5db31653ae13306eba
  end2Id: 4700dc2a5c00a4c48d17ea1d072be2ec
  ↓
Validar end1Id es business_application: ✓ SÍ
  ↓
Agregar a lista de eliminación ✓
  ↓
[MODO EJECUCIÓN] DELETE /4e574223f916f853a2f9832b6205e47d
  ✓ HTTP 204 OK
```

---

## Logging Detallado

Se generan logs en todos los niveles:
- **INFO:** Pasos principales, resúmenes
- **DEBUG:** Procesamiento detallado por relación
- **WARNING:** Recursos no encontrados, validaciones rechazadas
- **ERROR:** Fallos en DELETE, errores críticos

---

## Integración ITSM

**IMPORTANTE:** Esta funcionalidad es SOLO a nivel UCMDB.
- Las relaciones usage NO se procesan en ITSM
- Solo las relaciones con `relacion_fo=true` se procesan en ITSM
- Las relaciones usage son independientes del proceso ITSM
