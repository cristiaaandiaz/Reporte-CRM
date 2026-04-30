# DOCUMENTACIÓN TÉCNICA

## Script de Validación de Consistencia UCMDB-ITSM

### Descripción General

Este script valida la consistencia de NITs entre UCMDB e ITSM eliminando relaciones donde el NIT del cliente no coincide entre los dos extremos de la relación.

### Flujo de Datos

```
UCMDB API (Reporte JSON)
        ↓
    [Validación de NITs]
        ↓
   ┌───┴───┐
   │       │
Inconsistencias   →   Relaciones Usage
   Normales           de Servicecodes
   (con FO)           (business_app → sc)
   ↓                   ↓
UCMDB DELETE      UCMDB DELETE
   +                  +
ITSM PUT          (solo UCMDB)
(status=Removed)
```

## Arquitectura de Módulos

### src/main.py
Orquestador principal que coordina todo el flujo:
1. Autenticación UCMDB
2. Obtención del reporte JSON
3. Validación de integridad JSON
4. Procesamiento de inconsistencias
5. Eliminaciones en UCMDB e ITSM

### src/config.py
Configuración centralizada con classes:
- `ExecutionFlags`: Control de modo (simulación/ejecución)
- `ReportGenerationConfig`: Qué reportes generar
- `UCMDBConfig`: URLs, timeouts, credenciales UCMDB
- `ITSMConfig`: URL, credenciales ITSM
- `LoggingConfig`: Configuración de logging

### src/auth.py
Autenticación JWT con UCMDB:
- `obtener_token_ucmdb()`: Función principal
- `validar_credenciales()`: Verifica credenciales en .env
- `autenticar_con_api()`: Realiza POST al endpoint de auth
- `extraer_token_de_respuesta()`: Parsea respuesta JSON

### src/report.py
Consultas y validación de datos:
- `consultar_reporte_ucmdb()`: Descarga JSON grande (soporta retry)
- `filtrar_cis_por_tipo_servicecodes()`: Filtra CIs por tipo
- `validar_nit_en_relaciones_invertidas()`: Compara NITs
- `validar_relaciones_usage_de_servicecodes()`: Valida relaciones usage

### src/processor.py
Procesamiento de datos y archivos:
- `crear_directorio_ejecucion()`: Crea carpeta con timestamp
- `validar_integridad_json()`: Verifica estructura del JSON
- `guardar_reporte_json()`: Guarda copia del JSON
- `guardar_inconsistencias_detalle()`: Genera reporte de inconsistencias
- `enriquecer_inconsistencias_normales()`: Añade info de FO

### src/ucmdb_operations.py
Operaciones DELETE en UCMDB:
- `eliminar_en_ucmdb()`: Procesa inconsistencias normales
- `eliminar_relaciones_usage_de_servicecodes()`: Procesa usage
- `ejecutar_delete_ucmdb()`: DELETE con reintentos

### src/itsm_operations.py
Operaciones PUT en ITSM:
- `eliminar_en_itsm()`: Procesa solo relaciones con FO=true
- `consultar_parent_ci_en_itsm()`: GET para obtener ParentCI
- `ejecutar_update_itsm()`: PUT para marcar como Removed
- `_crear_headers_itsm()`: Genera Basic Auth

### src/logger_config.py
Configuración de logging:
- `LoggerFactory`: Factory para crear loggers configurados
- `obtener_logger()`: Función de conveniencia

## Algoritmos Principales

### Validación de NITs

```python
Para cada relación:
    1. Obtener end1Id y end2Id
    2. Obtener NIT de end1 (clr_onyxdb_company_nit)
    3. Obtener NIT de end2 (clr_onyxdb_companynit)
    4. Si NIT1 != NIT2 → marcar como inconsistencia
```

### Identificación de Foreign Object (FO)

```python
Para cada inconsistencia:
    1. Obtener end2Id de la relación
    2. Buscar relación CONTAINMENT donde end2Id = end2Id
    3. Verificar si end1Id es de tipo FO válido:
       - clr_service_catalog_fo_e
       - clr_service_catalog_fo_n
       - clr_service_catalog_fo_p
       - clr_service_catalog_fo_cloud
    4. Si es FO → marcar relacion_fo=True
```

### Eliminación en ITSM (2 pasos)

```python
1. GET /rest/Relationships?query=ChildCIs="<end2_id>"&view=expand
   → Obtiene ParentCI del JSON de respuesta

2. PUT /rest/cirelationship1to1s/{ParentCI}/{end2_id}
   → Body: {"cirelationship1to1": {"status": "Removed"}}
```

## Formato del JSON de UCMDB

```json
{
  "cis": [
    {
      "ucmdbId": "string",
      "type": "clr_onyxcrm|clr_onyxservicecodes|business_application|...",
      "label": "string",
      "properties": {
        "display_label": "string",
        "clr_onyxdb_company_nit": "string",
        "clr_onyxdb_companynit": "string"
      }
    }
  ],
  "relations": [
    {
      "ucmdbId": "string",
      "type": "ownership|containment|usage",
      "end1Id": "string",
      "end2Id": "string"
    }
  ]
}
```

## Códigos de Salida

| Código | Significado |
|--------|-------------|
| 0 | Éxito |
| 1 | Error de autenticación |
| 2 | Error al obtener reporte |
| 3 | Error de parsing JSON |
| 4 | Error de configuración |
| 5 | Error de ejecución |

## Configuración de Timeouts

En `src/config.py`:

- `CONNECT_TIMEOUT`: 60 segundos (conexión)
- `READ_TIMEOUT`: 3600 segundos (1 hora para archivos grandes)
- `REQUEST_TIMEOUT`: 30 segundos (peticiones individuales)
- `MAX_RETRIES`: 5 reintentos
- `RETRY_DELAY`: 15 segundos entre reintentos

## Consideraciones de Rendimiento

1. **Descarga grande**: El JSON puede ser de 250+ MB
2. **Logging de progreso**: Cada 50 MB se muestra progreso
3. **Recuperación de descarga truncada**: Intenta recuperar si se interrumpe
4. **Índices eficientes**: Usa diccionarios para búsqueda O(1)

## Pruebas

### Verificar sintaxis
```bash
python -m py_compile src/*.py
```

### Modo simulación (sin cambios reales)
```bash
python run.py
```

### Con reporte local
Editar `src/config.py`:
```python
USAR_REPORTE_LOCAL = True
```
Colocar JSON en `reports/reporte.json`