# 📚 Índice de Documentación - Script UCMDB

Bienvenido a la documentación técnica completa del **Script de Validación de NITs en UCMDB e ITSM**.

Esta documentación proporciona toda la información necesaria para entender, usar y mantener el script.

---

## 📖 Documentos Principales

### 1. 🚀 [**REFERENCIA_RAPIDA.md**](REFERENCIA_RAPIDA.md)
**Para:** Usuarios que necesitan empezar rápido  
**Duración de lectura:** 5-10 minutos

Incluye:
- ⚡ Inicio rápido en 5 minutos
- 🆘 Solución de problemas comunes
- 📋 Comandos útiles para debugging
- 💡 Tips y trucos
- 📁 Estructura de carpetas clave

**👉 COMIENZA AQUÍ si es tu primera vez**

---

### 2. 📋 [**DOCUMENTACION_TECNICA.md**](DOCUMENTACION_TECNICA.md)
**Para:** Desarrolladores que necesitan entender en profundidad  
**Duración de lectura:** 30-45 minutos

Incluye:
- 📝 Descripción completa del proyecto
- 🏗️ Estructura detallada del código
- 📊 Componentes principales explicados
- 🔄 Flujo de ejecución paso a paso
- 📈 Modelos de datos
- ⚙️ Configuración centralizada
- 🔐 Variables de entorno
- 📦 Guía de instalación
- 🎮 Guía de ejecución
- 📍 Códigos de salida
- 🛠️ Troubleshooting avanzado

**👉 LEE ESTO para entender completamente el script**

---

### 3. 📊 [**DIAGRAMAS_FLUJO.md**](DIAGRAMAS_FLUJO.md)
**Para:** Personas que aprenden visualmente  
**Duración de lectura:** 15-20 minutos

Incluye:
- 🔄 Diagrama de flujo principal
- 🔐 Flujo de autenticación
- 🌐 Flujo de descarga de reportes
- 🔍 Validación de NITs
- 💜 Enriquecimiento de datos
- 🗑️ Operaciones UCMDB
- 📤 Operaciones ITSM
- ⚠️ Manejo de errores y reintentos
- 📊 Generación de reportes
- ⚙️ Configuración y validación

**👉 USA ESTO para visualizar los procesos**

---

## 🎯 Cómo Usar esta Documentación

### Para Iniciarse Rápido
```
REFERENCIA_RAPIDA.md
    ↓
Lee "Inicio Rápido (5 Minutos)"
    ↓
Sigue los pasos de instalación
    ↓
Ejecuta en modo simulación
    ↓
¡Éxito!
```

### Para Desarrollo/Mantenimiento
```
DOCUMENTACION_TECNICA.md
    ↓
Lee la sección relevante:
├─ Componentes Principales
├─ Flujo de Ejecución
├─ Modelos de Datos
└─ Guía de Ejecución
    ↓
Consulta DIAGRAMAS_FLUJO.md si necesitas visualizar
    ↓
REFERENCIA_RAPIDA.md para comandos útiles
    ↓
Código fuente en src/
```

### Para Troubleshooting
```
¿Problema?
    ↓
REFERENCIA_RAPIDA.md → Sección "Errores Comunes"
    ↓
¿Sigue sin funcionar?
    ↓
DOCUMENTACION_TECNICA.md → Sección "Troubleshooting"
    ↓
¿Necesitas visualizar el flujo?
    ↓
DIAGRAMAS_FLUJO.md → Sección relevante
    ↓
Logs: logs/ucmdb_validation.log
```

---

## 📑 Mapa de Contenidos Rápido

### REFERENCIA_RAPIDA.md
- [⚡ Inicio Rápido](#-inicio-rápido-5-minutos)
- [📋 Modificar Flags de Control](#-modificar-flags-de-control)
- [🔄 Flujo de Ejecución](#-flujo-de-ejecución-paso-a-paso)
- [🆘 Comandos Útiles](#-comandos-útiles-para-debugging)
- [🐛 Errores Comunes](#-errores-comunes)
- [📊 Estructura de Reportes](#-estructura-de-reportes-generados)
- [🏗️ Estructura de Carpetas](#-estructura-de-carpetas-clave)
- [🔐 Seguridad](#-seguridad)

### DOCUMENTACION_TECNICA.md
- [📋 Descripción General](#1-descripción-general)
- [🏗️ Estructura del Proyecto](#2-estructura-del-proyecto)
- [💻 Componentes Principales](#3-componentes-principales)
- [🔄 Flujo de Ejecución](#4-flujo-de-ejecución)
- [📊 Diagrama de Flujo](#5-diagrama-de-flujo)
- [📈 Modelos de Datos](#6-modelos-de-datos)
- [⚙️ Configuración](#7-configuración)
- [🔒 Variables de Entorno](#8-variables-de-entorno)
- [📦 Instalación](#9-guía-de-instalación)
- [🎮 Ejecución](#10-guía-de-ejecución)
- [📍 Códigos de Salida](#11-códigos-de-salida)
- [🛠️ Troubleshooting](#12-troubleshooting)

### DIAGRAMAS_FLUJO.md
- [🔄 Flujo Principal](#1-flujo-principal-mainpy)
- [🔐 Autenticación](#2-flujo-de-autenticación-authpy)
- [🌐 Descargar Reportes](#3-flujo-de-descarga-de-reporte-reportpy)
- [🔍 Validación NITs](#4-flujo-de-validación-de-nits-reportpy)
- [💜 Enriquecimiento](#5-flujo-de-enriquecimiento-de-datos-processorpy)
- [🗑️ UCMDB DELETE](#6-flujo-de-eliminación-ucmdb-ucmdb_operationspy)
- [📤 ITSM PUT](#7-flujo-de-actualización-itsm-itsm_operationspy)
- [⚠️ Errores/Reintentos](#8-flujo-de-manejo-de-errores-y-reintentos)
- [📊 Reportes](#9-flujo-de-generación-de-reportes)
- [⚙️ Config/Validación](#10-flujo-de-configuración-y-validación)

---

## 🗂️ Estructura del Proyecto

```
Script UCMDB/
├── 📚 DOCUMENTACION_TECNICA.md     👈 Documentación completa
├── 📊 DIAGRAMAS_FLUJO.md           👈 Diagramas visuales
├── ⚡ REFERENCIA_RAPIDA.md         👈 Guía rápida
├── 📄 README.md                    👈 Info general
├── 📋 INDICE_DOCUMENTACION.md      👈 Este archivo
│
├── run.py                          # Punto de entrada
├── requirements.txt                # Dependencias
├── .env                            # Variables de entorno (NO commitear)
│
├── src/
│   ├── main.py                     # Lógica principal
│   ├── config.py                   # Configuración
│   ├── auth.py                     # Autenticación UCMDB
│   ├── report.py                   # Descargar reportes
│   ├── processor.py                # Procesar datos
│   ├── ucmdb_operations.py         # Operaciones UCMDB
│   ├── itsm_operations.py          # Operaciones ITSM
│   ├── logger_config.py            # Configuración logs
│   └── __init__.py
│
├── logs/
│   └── ucmdb_validation.log        # Archivo de logs
│
├── reports/                        # Reportes generados
│   ├── ejecucion_2026-01-30_12-24-37/
│   │   ├── reporte_*.json
│   │   ├── inconsistencias.txt
│   │   ├── inconsistencias_particulares.txt
│   │   └── resumen_itsm.txt
│   ├── ejecucion_2026-01-30_14-24-31/
│   └── ...
│
└── tests/
    └── __init__.py
```

---

## 🎓 Flujo de Aprendizaje Recomendado

### Nivel 1: Iniciarse Rápido ⭐
1. Lee [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#-inicio-rápido-5-minutos)
2. Instala y configura `.env`
3. Ejecuta: `python run.py` (modo simulación)
4. Mira los reportes generados

**Tiempo:** ~15 minutos  
**Resultado:** Script funcionando en tu máquina

---

### Nivel 2: Entender la Arquitectura ⭐⭐
1. Lee [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md#1-descripción-general)
2. Estudia [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)
3. Revisa el código fuente en `src/`
4. Prueba los flags de configuración

**Tiempo:** ~1 hora  
**Resultado:** Comprensión completa del script

---

### Nivel 3: Modificación y Extensión ⭐⭐⭐
1. Modifica `src/config.py` según necesidades
2. Agrega logging personalizado
3. Extiende funcionalidades
4. Lee secciones específicas de la documentación

**Tiempo:** Depende de cambios  
**Resultado:** Script personalizado

---

## 🔍 Buscar por Tema

### Quiero saber cómo...

#### ...instalar el script
→ [DOCUMENTACION_TECNICA.md - Instalación](DOCUMENTACION_TECNICA.md#9-guía-de-instalación)  
→ [REFERENCIA_RAPIDA.md - Inicio Rápido](REFERENCIA_RAPIDA.md#-inicio-rápido-5-minutos)

#### ...ejecutar el script
→ [DOCUMENTACION_TECNICA.md - Ejecución](DOCUMENTACION_TECNICA.md#10-guía-de-ejecución)  
→ [REFERENCIA_RAPIDA.md - Flujo de Ejecución](REFERENCIA_RAPIDA.md#-flujo-de-ejecución-paso-a-paso)

#### ...cambiar los flags de configuración
→ [REFERENCIA_RAPIDA.md - Modificar Flags](REFERENCIA_RAPIDA.md#-modificar-flags-de-control)  
→ [DOCUMENTACION_TECNICA.md - Configuración](DOCUMENTACION_TECNICA.md#7-configuración)

#### ...entender la estructura del código
→ [DOCUMENTACION_TECNICA.md - Componentes](DOCUMENTACION_TECNICA.md#3-componentes-principales)  
→ [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)

#### ...resolver un problema
→ [REFERENCIA_RAPIDA.md - Errores Comunes](REFERENCIA_RAPIDA.md#-errores-comunes)  
→ [DOCUMENTACION_TECNICA.md - Troubleshooting](DOCUMENTACION_TECNICA.md#12-troubleshooting)

#### ...entender el flujo de datos
→ [DOCUMENTACION_TECNICA.md - Flujo de Ejecución](DOCUMENTACION_TECNICA.md#4-flujo-de-ejecución)  
→ [DIAGRAMAS_FLUJO.md - Flujo Principal](DIAGRAMAS_FLUJO.md#1-flujo-principal-mainpy)

#### ...modificar autenticación
→ [DIAGRAMAS_FLUJO.md - Autenticación](DIAGRAMAS_FLUJO.md#2-flujo-de-autenticación-authpy)  
→ [DOCUMENTACION_TECNICA.md - auth.py](DOCUMENTACION_TECNICA.md#33-authpy---autenticación-ucmdb)

#### ...ver los reportes generados
→ [REFERENCIA_RAPIDA.md - Reportes](REFERENCIA_RAPIDA.md#-estructura-de-reportes-generados)  
→ [DOCUMENTACION_TECNICA.md - Reportes](DOCUMENTACION_TECNICA.md#guía-de-ejecución)

#### ...entender códigos de error
→ [DOCUMENTACION_TECNICA.md - Códigos de Salida](DOCUMENTACION_TECNICA.md#11-códigos-de-salida)

#### ...depurar el script
→ [REFERENCIA_RAPIDA.md - Debugging](REFERENCIA_RAPIDA.md#-comandos-útiles-para-debugging)  
→ [DOCUMENTACION_TECNICA.md - Logs](DOCUMENTACION_TECNICA.md#logging)

---

## ⚡ Acciones Rápidas

| Acción | Comando | Documentación |
|--------|---------|---------------|
| Instalar | `pip install -r requirements.txt` | [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md#pasos) |
| Ejecutar simulación | `python run.py` | [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#paso-1️⃣--prueba-segura-simulación) |
| Ver logs | `tail -f logs/ucmdb_validation.log` | [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#-comandos-útiles-para-debugging) |
| Ver últimos reportes | `ls -lt reports/*/reporte_*.json` | [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#paso-2️⃣--revisar-reportes) |
| Validar .env | `python -c "from src.config import *"` | [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md#variables-de-entorno) |
| Cambiar modo | Editar `src/config.py` | [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#-modificar-flags-de-control) |
| Revisar logs completo | `cat logs/ucmdb_validation.log` | [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md#logging) |
| Format JSON | `python -m json.tool reporte.json` | [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md#validar-json-de-reporte) |

---

## 🆘 Ayuda rápida

### Problema: No sé por dónde empezar
👉 Lee [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md)

### Problema: Script no funciona
👉 Revisa [Errores Comunes](REFERENCIA_RAPIDA.md#-errores-comunes)

### Problema: Quiero entender el código
👉 Estudia [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)

### Problema: Necesito visualizar procesos
👉 Mira [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)

### Problema: Necesito un comando específico
👉 Busca en [Comandos Útiles](REFERENCIA_RAPIDA.md#-comandos-útiles-para-debugging)

---

## 📚 Información Adicional

### Versión del Script
**Versión:** 1.0  
**Fecha Documentación:** Febrero 2026  
**Python:** 3.8+

### Dependencias Principales
- `requests` >= 2.28.1 (HTTP)
- `python-dotenv` >= 0.20.0 (Variables entorno)
- `urllib3` >= 1.26.0 (HTTP client)

### URLs Importantes (Dentro del Script)
- UCMDB Auth: `https://ucmdbapp.triara.co:8443/rest-api/authenticate`
- UCMDB API: `https://ucmdbapp.triara.co:8443/rest-api/topology`
- ITSM API: Definida en `.env` como `ITSM_URL`

---

## 📞 Soporte

### Código fuente
Revisar comentarios en archivos `.py` en `src/`

### Logs detallados
`logs/ucmdb_validation.log`

### Reportes generados
`reports/ejecucion_YYYY-MM-DD_HH-MM-SS/`

### Preguntas frecuentes
Revisar [Troubleshooting](DOCUMENTACION_TECNICA.md#12-troubleshooting)

---

## 🗺️ Navegación Cruzada

### Desde REFERENCIA_RAPIDA.md
- Necesitas más detalles → [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)
- Necesitas visualizar → [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)

### Desde DOCUMENTACION_TECNICA.md
- Necesitas ejemplo rápido → [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md)
- Necesitas visualizar → [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)

### Desde DIAGRAMAS_FLUJO.md
- Necesitas explicación → [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)
- Necesitas inicio rápido → [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md)

---

## ✅ Checklist de Primeros Pasos

- [ ] He leído [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md)
- [ ] He creado el archivo `.env` con credenciales
- [ ] He instalado las dependencias: `pip install -r requirements.txt`
- [ ] He ejecutado exitosamente en modo simulación
- [ ] He revisado los reportes generados
- [ ] He leído [DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)
- [ ] He entendido los diagramas en [DIAGRAMAS_FLUJO.md](DIAGRAMAS_FLUJO.md)
- [ ] Estoy listo para producción

---

**Última actualización:** Febrero 2026  
**Documentación Versión:** 1.0

---

### Atajos útiles

📍 [Inicio Rápido](REFERENCIA_RAPIDA.md#-inicio-rápido-5-minutos)  
📍 [Configuración](DOCUMENTACION_TECNICA.md#7-configuración)  
📍 [Ejecución](DOCUMENTACION_TECNICA.md#10-guía-de-ejecución)  
📍 [Troubleshooting](DOCUMENTACION_TECNICA.md#12-troubleshooting)  
📍 [Diagramas](DIAGRAMAS_FLUJO.md)

---

**¡Listo para empezar? Dirígete a [REFERENCIA_RAPIDA.md](REFERENCIA_RAPIDA.md)! 🚀**
