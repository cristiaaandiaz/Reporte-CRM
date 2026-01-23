# CHECKLIST DE VALIDACIÓN PARA PRODUCCIÓN

## 1. CONFIGURACIÓN Y CREDENCIALES

- [ ] Archivo `.env` creado con valores reales (no ejemplos)
- [ ] `ITSM_URL` configurada sin trailing slash: `https://servidor:puerto/SM/9/rest`
- [ ] `ITSM_USERNAME` y `ITSM_PASSWORD` verificados
- [ ] `UCMDB_URL` apunta a servidor correcto
- [ ] `UCMDB_USERNAME` y `UCMDB_PASSWORD` verificados
- [ ] Credenciales probadas en ambos sistemas antes de ejecutar script

## 2. CONFIGURACIÓN DEL SCRIPT

**En `main.py`, antes de CUALQUIER ejecución:**

```python
# Para primero test
MODO_EJECUCION = "simulacion"      # NO cambiar aún
GENERAR_RESUMEN = True              # Mantener en True
CREAR_CARPETA_EJECUCION = True     # Mantener en True
```

- [ ] `MODO_EJECUCION = "simulacion"` (**CRÍTICO PRIMERO**)
- [ ] `GENERAR_RESUMEN = True` (para auditoría y debugging)
- [ ] `CREAR_CARPETA_EJECUCION = True` (para guardar reportes)

## 3. EJECUCIÓN INICIAL (SIMULACIÓN)

```bash
python .\main.py
```

- [ ] Script ejecuta sin errores
- [ ] Se crea carpeta `reports/ejecucion_YYYY-MM-DD_HH-MM-SS/`
- [ ] Se genera `reporte_YYYY-MM-DD_HH-MM-SS.json` (reporte completo)
- [ ] Se genera `inconsistencias.txt` (relaciones a actualizar)
- [ ] Se genera `inconsistencias_particulares.txt`
- [ ] Se genera `resumen_itsm.txt` con estado "SIMULADA"

## 4. VALIDAR RESULTADOS DE SIMULACIÓN

**Abre `resumen_itsm.txt` y verifica:**

```
RESUMEN DE ACTUALIZACIONES EN ITSM
================================================================================
Fecha: 2026-01-22T...
Modo: SIMULACION
Método: PUT (Marcar como 'Removed')
================================================================================

1. ucmdbId: [relación_id]
   ucmdbid_fo: [fo_id]
   URL: https://servidor:puerto/SM/9/rest/cirelationship1to1s/[fo_id]/[relación_id]
   Método: PUT
   Body: {"cirelationship1to1": {"status": "Removed"}}
   Estado: SIMULADA
   Detalles: Listo para ejecutarse
```

- [ ] URLs son válidas y correctas
- [ ] `ucmdbid_fo` nunca es "N/A"
- [ ] Body tiene formato correcto
- [ ] Número de relaciones a procesar es razonable (revisar `inconsistencias.txt`)

## 5. VALIDACIÓN MANUAL (OPCIONAL PERO RECOMENDADO)

Antes de ejecutar, puede probar manualmente UNA relación:

```bash
# Test con curl (reemplazar variables)
curl -X PUT \
  "https://servidor:puerto/SM/9/rest/cirelationship1to1s/[fo_id]/[relation_id]" \
  -H "Authorization: Basic [credenciales_en_base64]" \
  -H "Content-Type: application/json" \
  -d '{"cirelationship1to1": {"status": "Removed"}}' \
  -k  # -k solo si certificado auto-firmado
```

- [ ] Request devuelve 200, 201, 202 o 204
- [ ] Sin errores 4xx o 5xx

## 6. PREPARAR PARA PRODUCCIÓN

**SOLO después de validar simulación:**

1. Editar `main.py`:
   ```python
   MODO_EJECUCION = "ejecucion"  # Cambiar SOLO aquí
   ```

2. Guardar archivo

- [ ] `MODO_EJECUCION = "ejecucion"` establecido
- [ ] Cambio confirmado en archivo
- [ ] Todas las validaciones anteriores completadas

## 7. EJECUCIÓN EN PRODUCCIÓN

**IMPORTANTE: Hacer durante ventana de mantenimiento**

```bash
python .\main.py
```

- [ ] Script inicia sin errores
- [ ] Logs muestran "[EJECUCIÓN]" (modo producción)
- [ ] URLs se procesan una a una
- [ ] Estados mostrados: "EXITOSA" o "FALLIDA"
- [ ] Reintentos automáticos si hay errores temporales
- [ ] Script finaliza sin excepciones no capturadas

## 8. VALIDACIÓN POST-EJECUCIÓN

**Revisar archivo `resumen_itsm.txt` generado:**

```
Total procesadas: [N]
Exitosas: [N éxito]
Fallidas: [M fallos]
```

- [ ] Número de "Exitosas" es significativo
- [ ] Si hay "Fallidas", revisar detalles del error
- [ ] Verificar en ITSM que relaciones estén marcadas como "Removed"
- [ ] Guardar resumen para auditoría

## 9. ROLLBACK (SI NECESARIO)

Si hay problemas en producción:

1. Cambiar `MODO_EJECUCION = "simulacion"` nuevamente
2. Revisar logs en `reports/` para entender qué falló
3. Verificar:
   - Conectividad ITSM
   - Credenciales
   - Formato de IDs
   - Permisos en ITSM

4. Contactar a administrador ITSM si:
   - API devuelve 401 (autenticación)
   - API devuelve 403 (autorización)
   - API devuelve 404 (endpoint incorrecto)

## 10. DOCUMENTACIÓN Y AUDITORÍA

**Archivos de auditoría generados:**

```
reports/
└── ejecucion_YYYY-MM-DD_HH-MM-SS/
    ├── reporte_YYYY-MM-DD_HH-MM-SS.json      # Datos originales
    ├── inconsistencias.txt                    # Relaciones a procesar
    ├── inconsistencias_particulares.txt       # Casos especiales
    └── resumen_itsm.txt                       # Resultado de operación
```

- [ ] Guardar carpeta `ejecucion_*` para auditoría
- [ ] Mantener por al menos 30 días
- [ ] Documentar fecha y hora de ejecución
- [ ] Documentar usuario que ejecutó script

## NOTAS IMPORTANTES

### Respuestas HTTP esperadas en ITSM:
- **200 OK**: Actualización exitosa
- **201 Created**: Recurso creado (aceptable)
- **202 Accepted**: Solicitud aceptada (puede procesar asincronamente)
- **204 No Content**: Exitoso sin contenido de respuesta
- **4xx Client Error**: Error permanente (no reintentar)
- **5xx Server Error**: Error temporal (reintentará 3 veces)

### Headers críticos:
- `Content-Type: application/json` ✓ Configurado
- `Accept: application/json` ✓ Configurado
- `Authorization: Basic [encoded_credentials]` ✓ Configurado

### Reintentos:
- Máximo 3 intentos por relación
- Delay entre intentos: 2 segundos
- Solo reintenta errores 5xx (temporales)

### Timeout:
- Conexión: 30 segundos
- Lectura: 30 segundos
- Total por relación: máximo 90 segundos (3 intentos × 30s)

### Validaciones automáticas:
- ✓ IDs no vacíos
- ✓ `ucmdbid_fo` no es "N/A"
- ✓ URL construida correctamente
- ✓ Payload JSON válido
- ✓ Headers autenticación presentes
