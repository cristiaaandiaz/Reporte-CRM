# Diagramas de Flujo Detallados - Script UCMDB

---

## 1. Flujo Principal (main.py)

```mermaid
graph TD
    START["🚀 Inicio: python run.py"] -->|Importar módulos| INIT["Inicializar Logger"]
    
    INIT --> VALIDATE["📋 main.py: validar_configuracion_inicial()"]
    VALIDATE -->|Fallo| ERR1["❌ EXIT_CONFIGURATION_ERROR"]
    VALIDATE -->|Éxito| LOG1["✅ Config válida"]
    
    LOG1 --> MKDIR["📁 crear_directorio_ejecucion()"]
    MKDIR --> FOLDER["📂 reports/ejecucion_YYYY-MM-DD_HH-MM-SS/"]
    
    FOLDER --> AUTH["🔐 obtener_token_ucmdb()"]
    AUTH -->|Success| TOKEN["✅ JWT Token obtenido"]
    AUTH -->|Fallo| ERR2["❌ EXIT_AUTH_ERROR"]
    
    TOKEN --> CHECK{¿USAR_REPORTE_LOCAL?}
    
    CHECK -->|True| LOAD1["📂 Cargar reports/reporte_test.json"]
    CHECK -->|False| LOAD2["🌐 consultar_reporte_ucmdb()"]
    
    LOAD1 --> PARSE["📄 json.load()"]
    LOAD2 --> PARSE
    
    PARSE -->|JSON inválido| ERR3["❌ EXIT_DATA_ERROR"]
    PARSE -->|JSON válido| DATA["✅ JSON parseado"]
    
    DATA --> PROCESAR["procesar_reporte()"]
    
    PROCESAR --> FILTER["🔍 filtrar_cis_por_tipo_servicecodes()"]
    FILTER --> FILTERED["Estado: CIs filtrados"]
    
    FILTERED --> VALIDATE_NIT["🔎 validar_nit_en_relaciones_invertidas()"]
    VALIDATE_NIT --> INCONS["Retorna: inconsistencias_normales, inconsistencias_particulares"]
    
    INCONS --> PREPINDEX["Preparar índices de relaciones"]
    PREPINDEX --> INDEX["relations_by_id, cis_by_id, containment_by_end2"]
    
    INDEX --> ENRICH1["💜 enriquecer_inconsistencias_normales()"]
    INDEX --> ENRICH2["💜 enriquecer_inconsistencias_particulares()"]
    
    ENRICH1 --> ENRICH_DATA["Agregar contexto: nombres CI, tipos relación"]
    ENRICH2 --> ENRICH_DATA
    
    ENRICH_DATA --> SAVE_JSON["💾 guardar_reporte_json()"]
    ENRICH_DATA --> SAVE_NORM["💾 guardar_inconsistencias_detalle()"]
    ENRICH_DATA --> SAVE_PART["💾 guardar_inconsistencias_detalle()"]
    
    SAVE_JSON --> CHECK_MODO{¿MODO_EJECUCION?}
    SAVE_NORM --> CHECK_MODO
    SAVE_PART --> CHECK_MODO
    
    CHECK_MODO -->|simulacion| SIMULATE["🟡 SIMULACIÓN"]
    CHECK_MODO -->|ejecucion| EXECUTE["🟢 EJECUCIÓN REAL"]
    
    SIMULATE --> SIM1["📋 Log: Registrar operaciones"]
    SIM1 --> SIM2["⚠️ SIN ejecutar cambios"]
    SIM2 --> SUMM["📊 Generar Resumen"]
    
    EXECUTE --> DEL["🗑️ eliminar_en_ucmdb()"]
    EXECUTE --> UPD["🔄 eliminar_en_itsm()"]
    
    DEL --> SUMM
    UPD --> SUMM
    
    SUMM --> SAVE_SUMM["📝 guardar_resumen_itsm.txt()"]
    SAVE_SUMM --> FINAL["✅ Ejecución completada"]
    FINAL --> EXIT0["EXIT 0: SUCCESS"]
    
    ERR1 --> CLEANUP["Limpiar recursos"]
    ERR2 --> CLEANUP
    ERR3 --> CLEANUP
    CLEANUP --> EXIT1["EXIT 1/2/3: error"]
```

---

## 2. Flujo de Autenticación (auth.py)

```mermaid
graph TD
    START["🔐 obtener_token_ucmdb()"] --> LOAD_CFG["Cargar UCMDBConfig"]
    
    LOAD_CFG --> VALIDATE_CRED["validar_credenciales()"]
    VALIDATE_CRED -->|Faltan| ERR1["❌ ConfigurationError"]
    VALIDATE_CRED -->|OK| BUILD_PAYLOAD["construir_payload_autenticacion()"]
    
    BUILD_PAYLOAD --> PAYLOAD["Crear JSON: {username, password, clientContext}"]
    
    PAYLOAD --> REQUEST["http.post() <- AUTH_URL"]
    REQUEST -->|ConnectionError| RETRY1["⚠️ Reintentos: 5"]
    REQUEST -->|Timeout| RETRY1
    RETRY1 -->|Agotados| ERR2["❌ AuthenticationError"]
    
    REQUEST -->|HTTP 200| PARSE_RESP["Parsear JSON response"]
    PARSE_RESP --> EXTRACT_TOKEN["token = response['token']"]
    EXTRACT_TOKEN --> DECODE_JWT["🔓 jwt.decode() validar firma"]
    DECODE_JWT -->|Inválido| ERR3["❌ Token inválido"]
    DECODE_JWT -->|Válido| SUCCESS["✅ Token obtenido"]
    
    SUCCESS --> RETURN_TOKEN["Retornar: token (string)"]
    RETURN_TOKEN --> END["Token usado en próximas requests"]
    
    ERR1 --> HANDLE_ERR["Logger.error()"]
    ERR2 --> HANDLE_ERR
    ERR3 --> HANDLE_ERR
    HANDLE_ERR --> RAISE["raise Exception"]
```

---

## 3. Flujo de Descarga de Reporte (report.py)

```mermaid
graph TD
    START["🌐 consultar_reporte_ucmdb()"] --> CREATE_SESSION["Crear requests.Session()"]
    
    CREATE_SESSION --> SETUP_RETRY["Configurar RetryStrategy"]
    SETUP_RETRY --> HEADERS["Preparar headers: {Authorization, Keep-Alive}"]
    
    HEADERS --> LOG_START["📝 Logger: Descargando reporte"]
    LOG_START --> MOUNT["Montar HTTPAdapterWithSocketKeepalive"]
    MOUNT --> TIMEOUT["Configurar timeout: (60s, 3600s)"]
    
    TIMEOUT --> REINTENTOS["for intento in range(MAX_RETRIES):"]
    
    REINTENTOS --> GET["session.get() <- UCMDB API"]
    GET -->|ConnectionError| RETRY_CONN["⚠️ Esperar 15s"]
    RETRY_CONN --> REINTENTOS
    
    GET -->|Timeout| RETRY_TIME["⚠️ Esperar 15s"]
    RETRY_TIME --> REINTENTOS
    
    GET -->|HTTP 200| STREAM["Readby_chunks(8192 bytes)"]
    STREAM --> BUFFER["Acumular en BytesIO"]
    BUFFER --> PROGRESS["Registrar progreso cada X bytes"]
    
    GET -->|HTTP 404| REPORT_NOT_FOUND["⚠️ Reporte no existe"]
    REPORT_NOT_FOUND --> ERR1["❌ ReportError"]
    
    GET -->|HTTP 403| NOT_AUTHORIZED["⚠️ Sin autorización"]
    NOT_AUTHORIZED --> ERR2["❌ AuthenticationError"]
    
    PROGRESS --> DONE_DOWNLOAD["Descarga completada"]
    DONE_DOWNLOAD --> VALIDATE_JSON["Validar JSON: json.loads()"]
    VALIDATE_JSON -->|Error| ERR3["❌ JSON inválido"]
    VALIDATE_JSON -->|OK| RETURN_STR["Retornar: JSON string"]
    
    RETURN_STR --> SUCCESS["✅ Datos listos para procesar"]
    
    ERR1 --> FINALLY["Cerrar sesión"]
    ERR2 --> FINALLY
    ERR3 --> FINALLY
    SUCCESS --> FINALLY
    FINALLY --> LOG_FINAL["Logger: Reporte obtenido"]
```

---

## 4. Flujo de Validación de NITs (report.py)

```mermaid
graph TD
    START["🔍 validar_nit_en_relaciones_invertidas()"] --> INIT["Inicializar listas"]
    INIT --> NORM_LIST["inconsistencias_normales = []"]
    INIT --> PART_LIST["inconsistencias_particulares = []"]
    
    NORM_LIST --> LOOP["for relacion in json['relations']:"]
    
    LOOP --> GET_END1["end1_id = relacion['end1Id']"]
    GET_END1 --> GET_END2["end2_id = relacion['end2Id']"]
    GET_END2 --> GET_NIT1["nit_end1 = relacion['properties']['clr_onyxdb_company_nit']"]
    GET_NIT1 --> GET_NIT2["nit_end2 = relacion['properties']['clr_onyxdb_companynit']"]
    
    GET_NIT2 --> CHECK_NIT1{¿nit_end1 es None?}
    
    CHECK_NIT1 -->|Sí| CHECK_NIT2{¿nit_end2 es None?}
    CHECK_NIT1 -->|No| CHECK_VACIO1{¿nit_end1 vacío?}
    
    CHECK_NIT2 -->|Ambos None| ADD_PART1["💜 Agregar a particulares: 'ambos_nulos'"]
    CHECK_NIT2 -->|Solo end2 None| ADD_PART2["💜 Agregar a particulares: 'nit_end2_nulo'"]
    
    CHECK_VACIO1 -->|Sí| ADD_PART3["💜 Agregar a particulares: 'nit_end1_vacio'"]
    CHECK_VACIO1 -->|No| CHECK_EQUAL{¿nit_end1 == nit_end2?}
    
    CHECK_EQUAL -->|Sí| LOG_OK["✅ NITs coinciden"]
    CHECK_EQUAL -->|No| IS_VALID["¿Ambos válidos?"]
    
    IS_VALID -->|Sí| ADD_NORM["📝 Agregar a normales: 'nit_mismatch'"]
    IS_VALID -->|No| ADD_PART4["💜 Agregar a particulares"]
    
    LOG_OK --> CONTINUE["Continuar siguiente relación"]
    ADD_NORM --> CONTINUE
    ADD_PART1 --> CONTINUE
    ADD_PART2 --> CONTINUE
    ADD_PART3 --> CONTINUE
    ADD_PART4 --> CONTINUE
    
    CONTINUE --> NEXT_REL{¿Más relaciones?}
    NEXT_REL -->|Sí| LOOP
    NEXT_REL -->|No| RETURN["Retornar tupla: (normales, particulares)"]
    
    RETURN --> STATS["📊 Estadísticas pendiente"]
    STATS --> END["Fin validación"]
```

---

## 5. Flujo de Enriquecimiento de Datos (processor.py)

```mermaid
graph TD
    START["💜 enriquecer_inconsistencias()"] --> INIT["Crear índices"]
    INIT --> IDX1["relations_by_id = {ucmdbId: relacion}"]
    INIT --> IDX2["cis_by_id = {ucmdbId: ci}"]
    INIT --> IDX3["containment_by_end2 = {end2Id: relacion}"]
    
    IDX1 --> LOOP["for inconsistencia in lista:"]
    
    LOOP --> GET_REL_ID["rel_id = inconsistencia['relation_id']"]
    GET_REL_ID --> LOOKUP_REL["relacion = relations_by_id.get(rel_id)"]
    
    LOOKUP_REL --> GET_E1["end1_id = relacion['end1Id']"]
    GET_E1 --> GET_E2["end2_id = relacion['end2Id']"]
    GET_E2 --> GET_TYPE["tipo_rel = relacion['type']"]
    
    GET_TYPE --> LOOKUP_E1["ci_end1 = cis_by_id.get(end1_id)"]
    LOOKUP_E1 --> LOOKUP_E2["ci_end2 = cis_by_id.get(end2_id)"]
    
    LOOKUP_E2 --> EXTRACT_E1["nombre_end1 = ci_end1['displayLabel']"]
    EXTRACT_E1 --> EXTRACT_E2["nombre_end2 = ci_end2['displayLabel']"]
    
    EXTRACT_E2 --> LOOKUP_CONT["containment = containment_by_end2.get(end2_id)"]
    
    LOOKUP_CONT --> ENRICH["Agregar campos: {"]
    ENRICH --> FIELD1["  'end1_name': nombre_end1,"]
    FIELD1 --> FIELD2["  'end2_name': nombre_end2,"]
    FIELD2 --> FIELD3["  'relation_type': tipo_rel,"]
    FIELD3 --> FIELD4["  'containment_info': {...},"]
    FIELD4 --> FIELD5["  'config_name': ...,"]
    FIELD5 --> FIELD6["  'estado': 'sin_procesar'"]
    FIELD6 --> CLOSE["}"]
    
    CLOSE --> APPEND["Agregar a resultado"]
    APPEND --> NEXT{¿Más inconsistencias?}
    
    NEXT -->|Sí| LOOP
    NEXT -->|No| RETURN["Retornar lista enriquecida"]
    
    RETURN --> COMPLETED["✅ Enriquecimiento completado"]
```

---

## 6. Flujo de Eliminación UCMDB (ucmdb_operations.py)

```mermaid
graph TD
    START["🗑️ eliminar_en_ucmdb()"] --> INIT["Inicializar: relaciones_procesadas = {}"]
    
    INIT --> CHECK_MODE{¿Simulación?}
    
    CHECK_MODE -->|Sí| LOG_SIM["📝 Registrar acciones sin ejecutar"]
    LOG_SIM --> RET_SIM["Retornar dict vacío (sin cambios)"]
    
    CHECK_MODE -->|No| LOOP["for inconsistencia in lista:"]
    
    LOOP --> EXTRACT["relation_id = inconsistencia['relation_id']"]
    EXTRACT --> BUILD_URL["Construir URL DELETE"]
    BUILD_URL --> URL["https://ucmdb.../dataModel/relation/{relation_id}"]
    
    URL --> HEADERS["Preparar headers: {Authorization: Bearer token}"]
    HEADERS --> DELETE_CALL["ejecutar_delete_ucmdb()"]
    
    DELETE_CALL --> FOR_RETRY["for intento in range(1, max_reintentos+1):"]
    
    FOR_RETRY --> REQ_DELETE["requests.delete(url, headers, verify=VERIFY_SSL)"]
    
    REQ_DELETE -->|ConnectionError| RETRY_DELAY["⏳ Esperar 2s"]
    RETRY_DELAY --> FOR_RETRY
    
    REQ_DELETE -->|Timeout| RETRY_DELAY
    
    REQ_DELETE -->|HTTP 200/204| LOG_OK["✅ DELETE exitoso"]
    REQ_DELETE -->|HTTP 404| LOG_NOT_FOUND["⚠️ Relación no encontrada"]
    REQ_DELETE -->|HTTP 403| LOG_FORBIDDEN["⚠️ Acceso denegado"]
    REQ_DELETE -->|HTTP 500| LOG_ERROR["❌ Error servidor"]
    
    LOG_OK --> RECORD_OK["Registrar: {estado: 'exito', status: 200}"]
    LOG_NOT_FOUND --> RECORD_4["Registrar: {estado: 'fallo', status: 404}"]
    LOG_FORBIDDEN --> RECORD_F["Registrar: {estado: 'fallo', status: 403}"]
    LOG_ERROR --> RETRY_DELAY
    
    RECORD_OK --> NEXT_REL{¿Más relaciones?}
    RECORD_4 --> NEXT_REL
    RECORD_F --> NEXT_REL
    
    NEXT_REL -->|Sí| LOOP
    NEXT_REL -->|No| RETURN["Retornar: relaciones_procesadas"]
    
    RETURN --> LOG_SUMMARY["📊 Resumen: X exitosas, Y fallidas"]
    LOG_SUMMARY --> END["Fin operación UCMDB"]
```

---

## 7. Flujo de Actualización ITSM (itsm_operations.py)

```mermaid
graph TD
    START["🔄 eliminar_en_itsm()"] --> INIT["Inicializar: relaciones_procesadas = {}"]
    
    INIT --> CHECK_MODE{¿Simulación?}
    
    CHECK_MODE -->|Sí| LOG_SIM["📝 Registrar actualizaciones sin ejecutar"]
    LOG_SIM --> RET_SIM["Retornar dict vacío (sin cambios)"]
    
    CHECK_MODE -->|No| LOOP["for inconsistencia in lista:"]
    
    LOOP --> EXTRACT["relation_id = inconsistencia['relation_id']"]
    EXTRACT --> BUILD_URL["Construir URL PUT"]
    BUILD_URL --> URL["ITSM_URL/relaciones/{relation_id}"]
    
    URL --> PAYLOAD["Crear payload: {\"state\": \"Removed\"}"]
    PAYLOAD --> HEADERS["Preparar headers:"]
    HEADERS --> AUTH["  Authorization: Basic {username:password en base64}"]
    AUTH --> CONTENT["  Content-Type: application/json"]
    
    CONTENT --> UPDATE_CALL["ejecutar_update_itsm()"]
    
    UPDATE_CALL --> FOR_RETRY["for intento in range(1, max_reintentos+1):"]
    
    FOR_RETRY --> REQ_PUT["requests.put(url, json=payload, headers, auth)"]
    
    REQ_PUT -->|ConnectionError| RETRY_DELAY["⏳ Esperar 2s"]
    RETRY_DELAY --> FOR_RETRY
    
    REQ_PUT -->|Timeout| RETRY_DELAY
    
    REQ_PUT -->|HTTP 200/201| LOG_OK["✅ PUT exitoso"]
    REQ_PUT -->|HTTP 404| LOG_NOT_FOUND["⚠️ Relación no existe en ITSM"]
    REQ_PUT -->|HTTP 401| LOG_UNAUTH["⚠️ Autenticación fallida"]
    REQ_PUT -->|HTTP 400| LOG_BADREQ["⚠️ Payload inválido"]
    REQ_PUT -->|HTTP 500| LOG_ERROR["❌ Error servidor"]
    
    LOG_OK --> RECORD_OK["Registrar: {estado: 'exito', status: 200}"]
    LOG_NOT_FOUND --> RECORD_4["Registrar: {estado: 'fallo', status: 404}"]
    LOG_UNAUTH --> RECORD_U["Registrar: {estado: 'fallo', status: 401}"]
    LOG_BADREQ --> RECORD_B["Registrar: {estado: 'fallo', status: 400}"]
    LOG_ERROR --> RETRY_DELAY
    
    RECORD_OK --> NEXT_REL{¿Más relaciones?}
    RECORD_4 --> NEXT_REL
    RECORD_U --> NEXT_REL
    RECORD_B --> NEXT_REL
    
    NEXT_REL -->|Sí| LOOP
    NEXT_REL -->|No| RETURN["Retornar: relaciones_procesadas"]
    
    RETURN --> LOG_SUMMARY["📊 Resumen: X actualizadas, Y fallidas"]
    LOG_SUMMARY --> END["Fin operación ITSM"]
```

---

## 8. Flujo de Manejo de Errores y Reintentos

```mermaid
graph TD
    START["⚠️ Solicitud HTTP"] --> TRY["try:"]
    
    TRY --> REQ["request (GET/POST/DELETE/PUT)"]
    
    REQ -->|ConnectionError| EXCEPT1["except ConnectionError:"]
    REQ -->|Timeout| EXCEPT2["except Timeout:"]
    REQ -->|RequestException| EXCEPT3["except RequestException:"]
    
    EXCEPT1 --> RETRYABLE1["¿Reintentable?"]
    EXCEPT2 --> RETRYABLE2["¿Reintentable?"]
    EXCEPT3 --> RETRYABLE3["¿Reintentable?"]
    
    RETRYABLE1 -->|Sí| WAIT1["⏳ time.sleep(delay)"]
    RETRYABLE2 -->|Sí| WAIT2["⏳ time.sleep(delay)"]
    RETRYABLE3 -->|Sí| WAIT3["⏳ time.sleep(delay)"]
    
    WAIT1 --> CHECK_COUNT1["¿intento < max_reintentos?"]
    WAIT2 --> CHECK_COUNT2["¿intento < max_reintentos?"]
    WAIT3 --> CHECK_COUNT3["¿intento < max_reintentos?"]
    
    CHECK_COUNT1 -->|Sí| RETRY1["↻ Reintentar"]
    CHECK_COUNT2 -->|Sí| RETRY2["↻ Reintentar"]
    CHECK_COUNT3 -->|Sí| RETRY3["↻ Reintentar"]
    
    RETRY1 --> REQ
    RETRY2 --> REQ
    RETRY3 --> REQ
    
    CHECK_COUNT1 -->|No| FAILED1["❌ Máximo de reintentos"]
    CHECK_COUNT2 -->|No| FAILED2["❌ Máximo de reintentos"]
    CHECK_COUNT3 -->|No| FAILED3["❌ Máximo de reintentos"]
    
    FAILED1 --> LOG_FAIL1["Logger.error(): Fallo después de X intentos"]
    FAILED2 --> LOG_FAIL2["Logger.error(): Fallo después de X intentos"]
    FAILED3 --> LOG_FAIL3["Logger.error(): Fallo después de X intentos"]
    
    RETRYABLE1 -->|No| FAIL_IMMED1["❌ Error no reintentable"]
    RETRYABLE2 -->|No| FAIL_IMMED2["❌ Error no reintentable"]
    RETRYABLE3 -->|No| FAIL_IMMED3["❌ Error no reintentable"]
    
    FAIL_IMMED1 --> LOG_FAIL_IMM1["Logger.error(): Error fatal"]
    FAIL_IMMED2 --> LOG_FAIL_IMM2["Logger.error(): Error fatal"]
    FAIL_IMMED3 --> LOG_FAIL_IMM3["Logger.error(): Error fatal"]
    
    LOG_FAIL1 --> RETURN_FALSE["return (False, mensaje_error)"]
    LOG_FAIL2 --> RETURN_FALSE
    LOG_FAIL3 --> RETURN_FALSE
    LOG_FAIL_IMM1 --> RETURN_FALSE
    LOG_FAIL_IMM2 --> RETURN_FALSE
    LOG_FAIL_IMM3 --> RETURN_FALSE
    
    REQ -->|HTTP 2xx| SUCCESS["✅ Éxito"]
    SUCCESS --> RETURN_TRUE["return (True, mensaje_exito)"]
    
    RETURN_FALSE --> END["Continuar con siguiente"]
    RETURN_TRUE --> END
```

---

## 9. Flujo de Generación de Reportes

```mermaid
graph TD
    START["📊 Generar Reportes"] --> INIT["Carpeta: reports/ejecucion_TIMESTAMP/"]
    
    INIT --> SAVE_JSON["guardar_reporte_json()"]
    SAVE_JSON --> JSON_FILE["✅ reporte_TIMESTAMP.json"]
    JSON_FILE --> JSON_CONTENT["Contenido: JSON completo"]
    
    JSON_CONTENT --> SAVE_NORM["guardar_inconsistencias_detalle()"]
    SAVE_NORM --> NORM_FILE["✅ inconsistencias.txt"]
    NORM_FILE --> NORM_CONTENT["Formato: Listado formateado"]
    
    NORM_CONTENT --> SAVE_PART["guardar_inconsistencias_detalle()"]
    SAVE_PART --> PART_FILE["✅ inconsistencias_particulares.txt"]
    PART_FILE --> PART_CONTENT["Formato: Casos especiales"]
    
    PART_CONTENT --> SAVE_SUMM["generar_resumen()"]
    SAVE_SUMM --> SUMM_FILE["✅ resumen_itsm.txt"]
    SUMM_FILE --> SUMM_CONTENT["Contenido:"]
    
    SUMM_CONTENT --> SUMM_STATS["- Estadísticas:"]
    SUMM_STATS --> SUMM_COUNT["  * Total inconsistencias"]
    SUMM_COUNT --> SUMM_NORM_C["  * Normales vs Particulares"]
    SUMM_NORM_C --> SUMM_DELETE["- Eliminaciones UCMDB:"]
    SUMM_DELETE --> SUMM_DELETE_OK["  * Exitosas: X"]
    SUMM_DELETE_OK --> SUMM_DELETE_FAIL["  * Fallidas: Y"]
    
    SUMM_DELETE_FAIL --> SUMM_UPDATE["- Actualizaciones ITSM:"]
    SUMM_UPDATE --> SUMM_UPDATE_OK["  * Exitosas: X"]
    SUMM_UPDATE_OK --> SUMM_UPDATE_FAIL["  * Fallidas: Y"]
    
    SUMM_UPDATE_FAIL --> SUMM_TIME["- Timestamps:"]
    SUMM_TIME --> SUMM_START["  * Inicio: TIMESTAMP"]
    SUMM_START --> SUMM_END["  * Fin: TIMESTAMP"]
    
    SUMM_END --> COPY_LOGS["Copiar logs"]
    COPY_LOGS --> LOG_FILE["logs/ucmdb_validation.log"]
    
    LOG_FILE --> FINAL["✅ Reportes generados"]
    FINAL --> LOCATION["📁 reports/ejecucion_YYYY-MM-DD_HH-MM-SS/"]
```

---

## 10. Flujo de Configuración y Validación

```mermaid
graph TD
    START["⚙️ Cargar Configuración"] --> LOAD_ENV[".env: load_dotenv()"]
    
    LOAD_ENV --> VALIDATE_ENV["Validar variables requeridas"]
    
    VALIDATE_ENV --> CHECK_UC_USER{¿UCMDB_USER?}
    CHECK_UC_USER -->|No| ERR_USER["❌ Error: UCMDB_USER faltante"]
    CHECK_UC_USER -->|Sí| CHECK_UC_PASS{¿UCMDB_PASS?}
    
    CHECK_UC_PASS -->|No| ERR_PASS["❌ Error: UCMDB_PASS faltante"]
    CHECK_UC_PASS -->|Sí| CHECK_ITSM_URL{¿ITSM_URL?}
    
    CHECK_ITSM_URL -->|No| ERR_URL["❌ Error: ITSM_URL faltante"]
    CHECK_ITSM_URL -->|Sí| CHECK_ITSM_USER{¿ITSM_USERNAME?}
    
    CHECK_ITSM_USER -->|No| ERR_ITSM_USER["❌ Error: ITSM_USERNAME faltante"]
    CHECK_ITSM_USER -->|Sí| CHECK_ITSM_PASS{¿ITSM_PASSWORD?}
    
    CHECK_ITSM_PASS -->|No| ERR_ITSM_PASS["❌ Error: ITSM_PASSWORD faltante"]
    CHECK_ITSM_PASS -->|Sí| ALL_VALID["✅ Todas las variables OK"]
    
    ERR_USER --> LOG_CRITICAL["Logger.critical()"]
    ERR_PASS --> LOG_CRITICAL
    ERR_URL --> LOG_CRITICAL
    ERR_ITSM_USER --> LOG_CRITICAL
    ERR_ITSM_PASS --> LOG_CRITICAL
    
    LOG_CRITICAL --> RAISE_ERR["raise ConfigurationError"]
    RAISE_ERR --> EXIT_CONFIG["EXIT 1: CONFIGURATION ERROR"]
    
    ALL_VALID --> VALIDATE_FLAGS["Validar flags en config.py"]
    
    VALIDATE_FLAGS --> CHECK_MODO{¿MODO_EJECUCION válido?}
    CHECK_MODO -->|No| ERR_MODO["❌ Debe ser: 'simulacion' o 'ejecucion'"]
    CHECK_MODO -->|Sí| CREATE_DIRS["Crear directorios base"]
    
    ERR_MODO --> RAISE_ERR
    
    CREATE_DIRS --> CREATE_REPORTS["mkdir -p reports/"]
    CREATE_REPORTS --> CREATE_LOGS["mkdir -p logs/"]
    CREATE_LOGS --> SUCCESS["✅ Configuración validada"]
    
    SUCCESS --> READY["Sistema listo para ejecutar"]
```

---

## Leyenda de Símbolos

| Símbolo | Significado |
|---------|------------|
| 🚀 | Inicio de proceso |
| 🛑 | Fin/Error fatal |
| ✅ | Éxito |
| ❌ | Error |
| ⚠️ | Advertencia/Problema |
| 📋 | Validación |
| 🔐 | Autenticación |
| 🌐 | Conexión/API |
| 📂 | Archivo/Carpeta |
| 🔍 | Búsqueda/Validación |
| 💜 | Enriquecimiento de datos |
| 🗑️ | Eliminación |
| 🔄 | Actualización |
| 📊 | Reporte/Estadística |
| 📝 | Logging/Registro |
| ⏳ | Espera/Delay |
| ↻ | Reintento |
| 🟡 | Simulación |
| 🟢 | Ejecución real |

---

**Fin de los Diagramas de Flujo Detallados**
