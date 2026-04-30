# AGENTS.md - Script UCMDB

## Propósito del Script
Valida la consistencia de NITs entre UCMDB e ITSM y elimina relaciones inconsistentes.
- Compara NITs en relaciones ownership entre `clr_onyxcrm` y `clr_onyxservicecodes`
- Elimina relaciones con NIT diferente en ambos extremos
- Sincroniza eliminaciones en dos sistemas: UCMDB (DELETE) e ITSM (PUT status=Removed)

## Entry Point
```bash
python run.py
```

## Configuración Crítica (src/config.py)

| Flag | Valores | Descripción |
|------|---------|-------------|
| `MODO_EJECUCION` | `"simulacion"` / `"ejecucion"` | `"simulacion"` = DRY-RUN (sin cambios reales) |
| `USAR_REPORTE_LOCAL` | `True` / `False` | `True` = usa JSON local, `False` = descarga de API |
| `VERIFY_SSL` | `"True"` / `"False"` en .env | `"True"` para producción |

## Variables de Entorno Requeridas (.env)
```
UCMDB_USER=...
UCMDB_PASS=...
ITSM_URL=http://servidor:puerto/SM/9/rest
ITSM_USERNAME=...
ITSM_PASSWORD=...
VERIFY_SSL=False
```

## Flujo de Ejecución

1. **PASO 1**: Autenticación UCMDB (obtiene JWT token)
2. **PASO 2**: Consulta reporte JSON desde UCMDB API
3. **PASO 3**: Procesa JSON y valida estructura
4. **PASO 4**: Crea directorio de ejecución con timestamp
5. **PASO 5**: Valida NITs en relaciones ownership
6. **PASO 6A**: Elimina relaciones en UCMDB (DELETE)
7. **PASO 6B**: Elimina relaciones usage en UCMDB
8. **PASO 6C**: Actualiza ITSM (PUT status=Removed)

## arquitectura

```
src/
├── main.py              # Orquestador del flujo completo
├── config.py            # TODA la configuración (flags, URLs, timeouts)
├── auth.py              # Autenticación JWT con UCMDB
├── report.py             # Consulta API y validación de NITs
├── processor.py          # Enriquecimiento y generación de reportes
├── ucmdb_operations.py   # DELETE en UCMDB
├── itsm_operations.py    # PUT en ITSM (marcado como Removed)
└── logger_config.py     # Configuración de logging
```

## Output
- **Reportes**: `reports/ejecucion_YYYY-MM-DD_HH-MM-SS/`
- **Logs**: `logs/ucmdb_validation.log`

## Pruebas en Simulación
```bash
# Verificar sintaxis
python -m py_compile src/*.py

# Ejecutar en modo simulación (sin cambios reales)
# Ya está configurado por defecto MODO_EJECUCION="simulacion"
python run.py
```

## Notas Importantes
- **SIEMPRE** ejecutar primero en modo simulación
- En simulación, no se hacen cambios reales en ningún sistema
- ITSM solo procesa relaciones con `relacion_fo=true` (contienen FO)
- La eliminación en ITSM requiere dos pasos: GET (obtener ParentCI) → PUT (marcar Removed)