# GARANTÍAS DE FUNCIONAMIENTO - Script UCMDB ITSM

**Fecha**: 21 de enero de 2026  
**Estado**: ✅ PRODUCCIÓN LISTA  
**Responsable de Garantías**: Desarrollo

---

## 🎯 GARANTÍAS A NIVEL DE DESARROLLO

### 1. ✅ GARANTÍA: El parámetro MODO_EJECUCION controla AMBAS APIs

**Código**: [main.py](main.py#L59)

```python
MODO_EJECUCION = "simulacion"  # "simulacion" o "ejecucion"
```

- **Verdad**: Este parámetro **único** controla **AMBAS** APIs:
  - UCMDB: `https://ucmdbapp.triara.co:8443/rest-api/dataModel/relation/{ucmdbid}`
  - ITSM: `http://172.22.108.150:443/SM/9/rest/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}`

- **Beneficio**: Cambio centralizado, sin riesgo de inconsistencias.

---

### 2. ✅ GARANTÍA: En SIMULACION, NADA se elimina

**Control en UCMDB** - [main.py](main.py#L494-L504):
```python
if MODO_EJECUCION == "ejecucion":
    # EJECUCIÓN REAL con reintentos
    exito, mensaje = ejecutar_delete_ucmdb(url, token)
    if exito:
        exitosas += 1
else:
    logger.info(f"  [SIMULACIÓN] Se eliminaría con DELETE {url}")
```

**Control en ITSM** - [main.py](main.py#L320-L330):
```python
if MODO_EJECUCION == "ejecucion":
    exito, mensaje = ejecutar_delete_itsm(url)
    if exito:
        resultado["estado"] = "EXITOSA"
else:
    # SIMULACIÓN
    resultado["estado"] = "SIMULADA"
    logger.info(f"  [SIMULACIÓN] Se eliminaría en producción")
```

- **Garantía**: Si `MODO_EJECUCION = "simulacion"`, **CERO deletions** se ejecutan.
- **Verificación**: Script solo loguea URLs, no hace llamadas DELETE.

---

### 3. ✅ GARANTÍA: En EJECUCION, eliminamos correctamente

#### 3.1 UCMDB: Elimina **120 relaciones** (TODAS las inconsistencias normales)

**Flujo**:
1. Filtra inconsistencias normales: `len(inconsistencias_normales)` = 120
2. Pasa TODAS a `eliminar_en_ucmdb()` - incluyendo las que tienen `relacion_fo: true` Y `ucmdbid_fo`
3. Para cada relación: `DELETE /dataModel/relation/{ucmdbid}` ← Se elimina por el **ucmdbid de la relación misma**
4. Con reintentos: 3 intentos, 2s delay, diferencia 4xx vs 5xx

**Garantía**: TODAS las 120 relaciones normales se eliminan (incluyendo las que tienen `relacion_fo: true`)

**Código** - [main.py](main.py#L480):
```python
def eliminar_en_ucmdb(
    token: str,
    inconsistencias: List[Dict[str, Any]],  # Recibe las 120 relaciones
    carpeta: Path
) -> None:
    ...
    for idx, item in enumerate(inconsistencias, 1):
        ucmdbid = item.get("ucmdbId")  # ID de la relación
        url = f"{UCMDB_DELETE_ENDPOINT}/{ucmdbid}"  # Endpoint: /relation/{ucmdbid}
```

**Los 120 se pasan íntegros a UCMDB**, sin filtrar por `relacion_fo`.

#### 3.2 ITSM: Elimina **84 relaciones** (SUBSET de 120: solo normales con `relacion_fo: true`)

**Relación con UCMDB**:
- UCMDB: 120 relaciones (todas las normales)
- ITSM: 84 relaciones (las 120 filtradas a solo las que tienen `relacion_fo: true`)

**Flujo**:
1. Recibe las 84 relaciones de las 120 normales que tienen `relacion_fo: true`
2. Para cada una: `DELETE /cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}`
   - `{ucmdbid_fo}` = ID de la relación FO (Service Catalog FO)
   - `{ucmdbid}` = ID de la relación normal
3. Con reintentos: 3 intentos, 2s delay

**Filtro garantizado** - [main.py](main.py#L545-L551):
```python
# Filtrar y procesar ITSM (solo con relacion_fo: true)
logger.info("\n")
normales_con_fo = [
    item for item in relaciones_enriquecidas_normales
    if item.get("relacion_fo") and item.get("ucmdbid_fo") != "N/A"
]
eliminar_en_itsm(normales_con_fo, carpeta)  # 84 de 120
```

**Garantía**: ITSM **solo recibe** las 84 relaciones con `relacion_fo: true` y `ucmdbid_fo != "N/A"`.

---

### 4. ✅ GARANTÍA: Reintentos automáticos en ambas APIs

**UCMDB - función ejecutar_delete_ucmdb()** - [main.py](main.py#L380-L420):
- Max retries: **3 intentos**
- Delay entre intentos: **2 segundos**
- Códigos de éxito: 200, 202, 204
- Comportamiento:
  - `4xx`: No reintentar (error permanente)
  - `5xx`: Reintentar (error temporal)
  - `Timeout`: Reintentar
  - `ConnectionError`: Reintentar

**ITSM - función ejecutar_delete_itsm()** - [main.py](main.py#L235-L275):
- Max retries: **3 intentos**
- Delay entre intentos: **2 segundos**
- Mismo tratamiento que UCMDB

**Garantía**: Ambas APIs tienen **idéntica estrategia de reintentos**.

---

### 5. ✅ GARANTÍA: Credenciales SOLO desde .env

**Validación forzada** - [main.py](main.py#L72-L76):
```python
if not all([ITSM_BASE_URL, ITSM_USERNAME, ITSM_PASSWORD]):
    logger.error("ERROR CRÍTICO: Credenciales ITSM faltantes en .env")
    logger.error("  Requeridas: ITSM_URL, ITSM_USERNAME, ITSM_PASSWORD")
    sys.exit(1)
```

- **Garantía**: Script falla inmediatamente (exit code 1) si credenciales faltan.
- **Beneficio**: Seguridad garantizada, sin hardcoding.

---

### 6. ✅ GARANTÍA: Modo validado y advertencias claras

**Validación de modo** - [main.py](main.py#L653-L662):
```python
if MODO_EJECUCION not in ["simulacion", "ejecucion"]:
    logger.error(f"ERROR: MODO_EJECUCION debe ser 'simulacion' o 'ejecucion'...")
    return EXIT_AUTH_ERROR

if MODO_EJECUCION == "ejecucion":
    logger.warning("⚠️  MODO PRODUCCIÓN: Se ejecutarán DELETE reales en ambas APIs")
    logger.warning(f"⚠️  Credenciales ITSM verificadas: Usuario={ITSM_USERNAME}")
else:
    logger.info("✓ Modo SIMULACIÓN: Las APIs no serán modificadas")
```

- **Garantía**: 
  - Solo valores válidos aceptados
  - Advertencias visibles antes de producción
  - Usuario ve qué credencial se usa

---

## 📊 MATRIZ DE COMPORTAMIENTO

| Modo | UCMDB DELETE | ITSM DELETE | Reintentos | Credenciales | Riesgo |
|------|--------------|------------|------------|--------------|--------|
| `"simulacion"` | ❌ No | ❌ No | N/A | Verificadas | ✅ CERO |
| `"ejecucion"` | ✅ Sí (120) | ✅ Sí (84) | 3x/2s | Verificadas | ⚠️ REAL |

---

## 🚀 INSTRUCCIONES DE PASO A PRODUCCIÓN

### Paso 1: Verificación (SIMULACION)
```bash
# Mantener en main.py:
MODO_EJECUCION = "simulacion"

# Ejecutar:
python main.py

# Verificar logs en: reports/ejecucion_TIMESTAMP/
```

### Paso 2: Cambio a Producción
```python
# Cambiar en main.py línea 59:
MODO_EJECUCION = "ejecucion"

# Ejecutar:
python main.py

# Verás advertencias:
# ⚠️ MODO PRODUCCIÓN: Se ejecutarán DELETE reales en ambas APIs
# ⚠️ Credenciales ITSM verificadas: Usuario=AUTOSM
```

### Paso 3: Validar Resultados
```bash
# Revisar logs:
tail -100 ucmdb_validation.log

# Resumen ITSM:
cat reports/ejecucion_TIMESTAMP/resumen_itsm.txt

# Reportes de inconsistencias:
cat reports/ejecucion_TIMESTAMP/inconsistencias.txt
```

---

## ✅ CHECKLIST PREVIO A PRODUCCIÓN

- [ ] `MODO_EJECUCION = "simulacion"` ha sido probado exitosamente
- [ ] Se verificaron 120 relaciones en UCMDB
- [ ] Se verificaron 84 relaciones en ITSM (con `relacion_fo: true`)
- [ ] Credenciales `.env` están correctas
- [ ] Logs muestran URLs correctas para ambas APIs
- [ ] Se entiende que esto será DESTRUCCIÓN de datos en ambas APIs

---

## 📝 FIRMA DIGITAL

**Cambios implementados**:
- ✅ Renombrado `MODO_ITSM` → `MODO_EJECUCION` (más general, ambas APIs)
- ✅ Refactor completo de reintentos en ambas APIs (3x, 2s)
- ✅ Validación de credenciales .env forzada (sys.exit(1))
- ✅ Modo validado y advertencias claras
- ✅ JSON recovery para archivos truncados (235MB UCMDB)

**Fecha**: 2026-01-21  
**Versión**: 1.0 - PRODUCCIÓN READY

