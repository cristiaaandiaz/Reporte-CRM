# Guía de Referencia Rápida - Script UCMDB

**Uso rápido:** Consulta esta guía para acciones comunes sin leer toda la documentación.

---

## ⚡ Inicio Rápido (5 Minutos)

### 1. Instalación
```bash
cd "Script UCMDB"
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 2. Configurar `.env`
```bash
# Crear .env en raíz del proyecto
UCMDB_USER=tu_usuario
UCMDB_PASS=tu_password
ITSM_URL=https://itsm.ejemplo.com/api
ITSM_USERNAME=usuario_itsm
ITSM_PASSWORD=password_itsm
VERIFY_SSL=False         # Solo desarrollo
```

### 3. Ejecutar (Simulación = Segura)
```bash
# En config.py, asegurar:
# ExecutionFlags.MODO_EJECUCION = "simulacion"
# ExecutionFlags.USAR_REPORTE_LOCAL = True

python run.py
```

### 4. Ver Resultados
```bash
# Reportes generados en:
reports/ejecucion_YYYY-MM-DD_HH-MM-SS/
├── reporte_TIMESTAMP.json
├── inconsistencias.txt
├── inconsistencias_particulares.txt
└── resumen_itsm.txt

# Logs:
logs/ucmdb_validation.log
```

---

## 📋 Modificar Flags de Control

**Archivo:** `src/config.py`

```python
class ExecutionFlags:
    # Cambiar AQUÍ:
    MODO_EJECUCION = "simulacion"      # "simulacion" o "ejecucion"
    USAR_REPORTE_LOCAL = False         # True para JSON local
    GENERAR_RESUMEN = True             # Generar reportes
    CREAR_CARPETA_EJECUCION = True     # Carpeta con timestamp
```

| Flag | Opción 1 | Opción 2 | Recomendado |
|------|----------|----------|------------|
| MODO | "simulacion" | "ejecucion" | simulacion (primero) |
| USAR_REPORTE_LOCAL | True | False | True (desarrollo) |
| GENERAR_RESUMEN | True | False | True (siempre) |
| CREAR_CARPETA | True | False | True (mejor) |

---

## 🔄 Flujo de Ejecución Paso a Paso

### Paso 1️⃣ : PRUEBA SEGURA (Simulación)
```python
# config.py
ExecutionFlags.MODO_EJECUCION = "simulacion"
ExecutionFlags.USAR_REPORTE_LOCAL = True
```
```bash
python run.py
```
✅ **No cambia nada en BD**  
✅ Muestra qué haría  
✅ Genera reportes análisis

### Paso 2️⃣ : REVISAR REPORTES
```bash
# Ver resumen ejecutivo
cat reports/ejecucion_*/resumen_itsm.txt

# Examinar inconsistencias encontradas
cat reports/ejecucion_*/inconsistencias.txt

# Validar JSON completo
python -m json.tool reports/ejecucion_*/reporte_*.json | less
```

### Paso 3️⃣ : EJECUTACIÓN REAL (Cuando esté seguro)
```python
# config.py
ExecutionFlags.MODO_EJECUCION = "ejecucion"    # CAMBIAR A REAL
ExecutionFlags.USAR_REPORTE_LOCAL = False      # USAR API UCMDB
```
```bash
python run.py
```
⚠️ **ESTO CAMBIA DATOS EN UCMDB e ITSM**  
💾 **CAMBIOS PERMANENTES**  
📝 **Todos se registran en logs**

---

## 🔄 Flujo ITSM: Obtener ParentCI y Marcar Removed

### ¿Por qué dos pasos?

ITSM requiere el `ParentCI` (aplicación/servicio) para marcar relaciones como "Removed". 
El script primero consulta el ParentCI y luego ejecuta la eliminación.

### Paso 1: GET ParentCI

```http
GET /SM/9/rest/Relationships?query=ChildCIs="<end2Id>"&view=expand
```

**Respuesta típica:**
```json
{
  "content": [{
    "Relationship": {
      "ParentCI": "Empresas – Intranet_901999048-9",
      "RelationshipType": "Containment"
    }
  }]
}
```

### Paso 2: PUT Marcar Removed

```http
PUT /SM/9/rest/cirelationship1to1s/{ParentCI}/{end2Id}

{
  "cirelationship1to1": {
    "status": "Removed"
  }
}
```

### En los Logs

```
[1/145] Procesando relación: 496c7e40973e112d8a374bb29fa5ed75
  NIT: 901999048-9 ≠ 860512780-4
  End1: UNION TEMPORAL SITEC_901999048-9_13992759 (...)
  End2: AABIXG0070 (4a2713dcf16b910c9ec1a760edcd901f)
  
  → Paso 1: GET Relationship para obtener ParentCI...
  ✓ ParentCI obtenido: Empresas – Intranet_901999048-9
  [SIM] PUT http://172.22.108.160:13090/SM/9/rest/cirelationship1to1s/Empresas – Intranet_901999048-9/4a2713dcf16b910c9ec1a760edcd901f
```

---

### Ver logs en tiempo real
```bash
# Terminal 1:
tail -f logs/ucmdb_validation.log

# Terminal 2:
python run.py
```

### Llenar logs con nivel DEBUG
```python
# En main.py, agregar:
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Validar JSON de reporte
```bash
python -c "
import json
with open('reports/reporte_test.json') as f:
    data = json.load(f)
    print(f'Total CIs: {len(data.get(\"cis\", []))}')
    print(f'Total relaciones: {len(data.get(\"relations\", []))}')
"
```

### Contar inconsistencias encontradas
```bash
python -c "
import json
from pathlib import Path

for reporte in Path('reports').glob('**/reporte_*.json'):
    print(f'Reporte: {reporte.parent.name}')
    with open(reporte) as f:
        # Lógica de conteo aquí
        pass
"
```

### Verificar credenciales
```bash
# En PowerShell:
$env:UCMDB_USER = "test"
$env:UCMDB_PASS = "test"
$env:ITSM_URL = "https://..."

python run.py
```

---

## 🐛 Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `ModuleNotFoundError: No module named 'src'` | Ejecutando desde carpeta equivocada | Estar en raíz del proyecto |
| `ConfigurationError: Credenciales faltantes` | .env no existe o incompleto | Crear/completar .env |
| `ConnectionError: Failed to establish connection` | UCMDB no accesible | Verificar URL, firewall |
| `Timeout: Read timed out` | Descarga muy lenta | Aumentar READ_TIMEOUT en config.py |
| `SSL: certificate_verify_failed` | VERIFY_SSL=True en desarrollo | Cambiar a False en .env |
| `JSONDecodeError: Invalid JSON` | Reporte corrompido | Usar reporte local válido |
| `FileNotFoundError: reports/reporte_test.json` | Archivo no existe | Descargar de API o crear/proporcionar |
| `PermissionError: [Errno 13]` | Permisos insuficientes en carpeta | Ejecutar como admin o ajustar permisos |

---

## 📊 Estructura de Reportes Generados

### `reporte_TIMESTAMP.json`
```json
{
  "cis": [...],           // Componentes de configuración
  "relations": [...]      // Relaciones entre CIs
}
```
**Uso:** Análisis completo, auditoría, restauración

---

### `inconsistencias.txt`
```
================================================================================
INCONSISTENCIAS
================================================================================

[1] Relación: UCMDB-ID-123
    Type: clr_rel_companybranch
    End1: CI-001 (Empresa A)
    End2: CI-002 (Sucursal B)
    NIT End1: 1000000001
    NIT End2: 1000000002
    Tipo: nit_mismatch
    Estado: sin_procesar

[2] Relación: UCMDB-ID-124
    ...
```
**Uso:** Revisión por analistas, aprobaciones

---

### `inconsistencias_particulares.txt`
```
================================================================================
INCONSISTENCIAS PARTICULARES
================================================================================

[1] Relación: UCMDB-ID-456
    Type: clr_rel_companybranch
    Problema: clr_onyxdb_companynit es NULL
    Estado: sin_procesar

[2] Relación: UCMDB-ID-457
    Problema: Ambos NITs son nulos
    Estado: sin_procesar
```
**Uso:** Casos especiales que requieren atención manual

---

### `resumen_itsm.txt`
```
================================================================================
RESUMEN DE EJECUCIÓN
================================================================================

CONFIGURACIÓN:
  Modo: simulacion
  Usar Reporte Local: True
  Generar Resumen: True
  
ESTADÍSTICAS:
  Total CIs filtrados: 500
  Total relaciones: 1250
  
INCONSISTENCIAS DETECTADAS:
  Normales: 45
  Particulares: 12
  Total: 57

OPERACIONES UCMDB (eliminar relaciones):
  Modo simulación: cambios NO ejecutados
  Registradas: 45
  
OPERACIONES ITSM (marcar como Removed):
  Modo simulación: cambios NO ejecutados
  Registradas: 45

TIMESTAMPS:
  Inicio: 2026-02-17 12:30:00
  Fin: 2026-02-17 12:35:15
  Duración: 5 minutos 15 segundos
```

---

## 🏗️ Estructura de Carpetas Clave

```
src/
├── main.py              # 🎯 AQUÍ: lógica principal
├── config.py            # ⚙️ AQUÍ: cambiar flags
├── auth.py              # 🔐 Autenticación UCMDB
├── report.py            # 📊 Descargar reportes
├── processor.py         # 💾 Procesar datos
├── ucmdb_operations.py  # 🗑️ Eliminar en UCMDB
└── itsm_operations.py   # 🔄 Actualizar en ITSM

reports/
└── ejecucion_YYYY-MM-DD_HH-MM-SS/
    ├── reporte_TIMESTAMP.json
    ├── inconsistencias.txt
    ├── inconsistencias_particulares.txt
    └── resumen_itsm.txt

logs/
└── ucmdb_validation.log         # 📝 TODO se registra aquí
```

---

## 🔐 Seguridad

⚠️ **NUNCA comitear `.env` con credenciales reales**

```bash
# .gitignore
.env
.env.local
venv/
__pycache__/
*.pyc
*.log
```

✅ **Buenas prácticas:**
- Usar variables de entorno
- Logs nunca incluyen passwords
- SSL verificado en producción
- Modo simulación antes de ejecutar

---

## 📈 Escalabilidad

### Reportes Grandes (>250 MB)
```python
# config.py - UCMDBConfig
CONNECT_TIMEOUT = 60
READ_TIMEOUT = 7200      # Aumentar a 2+ horas
```

### Muchas Relaciones (>10,000)
- Script procesa automáticamente
- Usa índices para O(1) lookups
- Optimizado para memoria

### Múltiples Ejecuciones
- Cada una crea carpeta única
- Histórico completo preservado
- Logs se acumulan (rotación recomendada)

---

## 🔄 Re-ejecutar Análisis

Si necesitas re-run sin cambios:

```python
# config.py
ExecutionFlags.MODO_EJECUCION = "simulacion"    # Siempre seguro
ExecutionFlags.USAR_REPORTE_LOCAL = True        # Rápido
ExecutionFlags.GENERAR_RESUMEN = True           # Genera reportes

# Ejecutar
python run.py

# Ver resultados
cat reports/ejecucion_*/resumen_itsm.txt
```

---

## 📞 Contacto y Escaladas

### Problema: Script está lento
1. Revisar logs: `tail -f logs/ucmdb_validation.log`
2. Puede ser red lenta → aumentar timeouts
3. Contactar admin infraestructura

### Problema: Autenticación falla
1. Verificar credenciales en .env
2. Contactar admin UCMDB/ITSM
3. Validar permisos de cuenta

### Problema: Datos inconsistentes
1. Generar reporte detallado en simulación
2. Revisar `inconsistencias.txt` y `inconsistencias_particulares.txt`
3. Escalar con reportes adjuntos

---

## 💡 Tips y Trucos

### Guardar reporte como referencia
```bash
# Respaldar reporte importante
cp -r reports/ejecucion_2026-02-17_12-20-35 \
      reports/BACKUP_PROD_2026-02-17
```

### Buscar relación específica en JSON
```bash
python -c "
import json
rel_id = 'UCMDB-123'
with open('reports/ejecucion_*/reporte_*.json') as f:
    data = json.load(f)
    for rel in data['relations']:
        if rel['ucmdbId'] == rel_id:
            print(json.dumps(rel, indent=2))
            break
"
```

### Contar éxitos vs fallos
```bash
grep "EXIT 0:" logs/ucmdb_validation.log | wc -l
```

### En caso de rollback
1. Las operaciones se registran con timestamp
2. Reversible manualmente en UCMDB
3. Contactar admin si necesita rollback

---

## 🎓 Próximos Pasos

1. **Leer:** [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md) - Completa y detallada
2. **Entender:** [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md) - Flujos visuales
3. **Practicar:** Ejecutar en simulación primero
4. **Escalar:** Contactar admin para ejecución en producción

---

**Última actualización:** Febrero 2026  
**Versión:** 1.0
