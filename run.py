#!/usr/bin/env python3
"""
Entry Point Principal del Script de Validación de NITs.

Este archivo actúa como punto de entrada único para ejecutar el script.
Permite ejecutar desde la raíz del proyecto sin navegar a módulos internos.

Uso:
    python run.py

Variables de entorno requeridas en .env:
    UCMDB_USER: Usuario para autenticación UCMDB
    UCMDB_PASS: Contraseña para autenticación UCMDB
    ITSM_URL: URL base de la API ITSM
    ITSM_USERNAME: Usuario para ITSM
    ITSM_PASSWORD: Contraseña para ITSM

Para parametrizar qué reportes se generan, edita src/config.py:
    ReportGenerationConfig.REPORTE_JSON = True/False
    ReportGenerationConfig.INCONSISTENCIAS = True/False
    ReportGenerationConfig.INCONSISTENCIAS_PARTICULARES = True/False
    ReportGenerationConfig.RESUMEN_UCMDB = True/False
    ReportGenerationConfig.RESUMEN_ITSM = True/False
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path
root_path = Path(__file__).parent
sys.path.insert(0, str(root_path))

from src.config import ReportGenerationConfig
from src.main import main

if __name__ == "__main__":
    # Mostrar configuración de reportes
    ReportGenerationConfig.mostrar_config()
    
    # Ejecutar script principal
    sys.exit(main())
