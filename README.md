# Script de Validación de Consistencia UCMDB-ITSM

**Versión:** 2.0  
**Fecha:** Abril 2026

Este script valida y elimina relaciones inconsistentes entre UCMDB e ITSM comparando NITs de clientes.

## Propósito

El script выполняет следующие функции:

1. **Validación de NITs**: Compara el NIT del cliente en las relaciones ownership entre `clr_onyxcrm` (CRM) y `clr_onyxservicecodes` (ServiceCodes)
2. **Eliminación de Inconsistencias**: Elimina relaciones donde el NIT no coincide en ambos extremos
3. **Sincronización Dual**: Ejecuta eliminaciones en ambos sistemas:
   - UCMDB: DELETE directo de relaciones
   - ITSM: PUT con status="Removed"

## Requisitos

- Python 3.8+
- Dependencias: `requests`, `python-dotenv` (ver `requirements.txt`)

## Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con las credenciales correctas
```

## Configuración (.env)

```env
# UCMDB
UCMDB_USER=tu_usuario
UCMDB_PASS=tu_password

# ITSM (URL base sin endpoint adicional)
ITSM_URL=http://servidor:puerto/SM/9/rest
ITSM_USERNAME=tu_usuario_itsm
ITSM_PASSWORD=tu_password_itsm

# SSL (False para certificados auto-firmados)
VERIFY_SSL=False
```

## Uso

### Modo Simulación (Recomendado para pruebas)

```bash
python run.py
```

Este modo muestra las operaciones que se realizarán sin ejecutar cambios reales.

### Modo Ejecución (Producción)

Editar `src/config.py` y cambiar:

```python
MODO_EJECUCION = "ejecucion"  # Cambiar de "simulacion" a "ejecucion"
```

Luego ejecutar:

```bash
python run.py
```

## Estructura del Proyecto

```
Script UCMDB/
├── run.py                     # Entry point
├── src/
│   ├── main.py                # Orquestador del flujo
│   ├── config.py              # Configuración centralizada
│   ├── auth.py                # Autenticación UCMDB (JWT)
│   ├── report.py              # Consulta y validación de datos
│   ├── processor.py          # Procesamiento y generación de reportes
│   ├── ucmdb_operations.py    # DELETE en UCMDB
│   ├── itsm_operations.py    # PUT en ITSM
│   └── logger_config.py      # Configuración de logging
├── reports/                   # Reportes generados (carpetas con timestamp)
├── logs/                      # Archivos de log
└── .env                       # Credenciales (no incluir en git)
```

## Flujo de Ejecución

1. **Autenticación**: Obtiene token JWT de UCMDB
2. **Consulta**: Descarga reporte JSON desde UCMDB API
3. **Validación**: Procesa JSON y valida consistencia de NITs
4. **Reporte**: Genera archivos con inconsistencias encontradas
5. **Eliminación UCMDB**: DELETE de relaciones inconsistentes
6. **Eliminación Usage**: DELETE de relaciones usage vinculadas a servicecodes
7. **Actualización ITSM**: PUT para marcar relaciones como "Removed"

## Reportes Generados

Los reportes se guardan en carpetas con timestamp: `reports/ejecucion_YYYY-MM-DD_HH-MM-SS/`

| Archivo | Descripción |
|---------|-------------|
| `reporte_*.json` | Copia del JSON descargado de UCMDB |
| `inconsistencias.txt` | Detalle de relaciones con NITs不一致 |
| `resumen_ucmdb.txt` | Resumen de operaciones DELETE en UCMDB |
| `resumen_eliminacion_usage.txt` | Resumen de eliminación de relaciones usage |
| `resumen_itsm.txt` | Resumen de operaciones PUT en ITSM |

## Flags de Configuración

En `src/config.py`:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MODO_EJECUCION` | `"simulacion"` | Modo simulación o ejecución |
| `USAR_REPORTE_LOCAL` | `False` | Usar JSON local en lugar de API |
| `CREAR_CARPETA_EJECUCION` | `True` | Crear carpeta con timestamp |
| `REPORTE_JSON` | `True` | Guardar copia del JSON |
| `INCONSISTENCIAS` | `True` | Guardar detalle de inconsistencias |
| `RESUMEN_UCMDB` | `True` | Guardar resumen de operaciones UCMDB |
| `RESUMEN_ITSM` | `True` | Guardar resumen de operaciones ITSM |

## Logging

Los logs se guardan en:
- Consola (nivel INFO)
- `logs/ucmdb_validation.log` (nivel DEBUG)

## Recomendaciones de Seguridad

1. **Siempre ejecutar en modo simulación primero**
2. **Verificar los reportes generados** antes de cambiar a modo ejecución
3. **Respaldar datos** antes de ejecutar en producción
4. **Ejecutar durante ventana de mantenimiento**
5. **No incluir .env en control de versiones**

## Troubleshooting

### Error de autenticación
Verificar que `UCMDB_USER` y `UCMDB_PASS` estén correctos en `.env`.

### Timeout en descarga de reporte
Aumentar `READ_TIMEOUT` en `src/config.py` (actualmente 3600 segundos para archivos grandes).

### Error en ITSM
Verificar que `ITSM_URL` tenga el formato correcto: `http://servidor:puerto/SM/9/rest` (sin `/cirelationship1to1s` al final).

### Verificación SSL deshabilitada
Si se muestra la advertencia, establecer `VERIFY_SSL=True` en `.env` para producción.

## Tests

### Ejecutar tests unitarios
```bash
python -m pytest tests/ -v
```

### Resultados
- **71 tests** pasando
- Cobertura: config, auth, report, processor, ucmdb_operations, itsm_operations

## Estructura de Tests

```
tests/
├── conftest.py                 # Fixtures y configuración
├── test_config.py             # Tests de configuración
├── test_auth.py               # Tests de autenticación
├── test_report.py             # Tests de validación de datos
├── test_processor.py          # Tests de procesamiento
├── test_ucmdb_operations.py   # Tests de operaciones UCMDB
└── test_itsm_operations.py    # Tests de operaciones ITSM
```

## Verificaciones Pre-Deployment

```bash
# 1. Verificar sintaxis
python -m py_compile src/*.py

# 2. Ejecutar tests
python -m pytest tests/ -v

# 3. Ejecutar en modo simulación
python run.py

# 4. Revisar reportes generados
ls reports/ejecucion_*/
```

## Licencia
Uso interno - Triara