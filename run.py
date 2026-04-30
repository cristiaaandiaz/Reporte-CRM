#!/usr/bin/env python3
"""
Entry Point Principal del Script de Validación de NITs.
Uso: python run.py
"""

import sys
from pathlib import Path

root_path = Path(__file__).parent
sys.path.insert(0, str(root_path))

from src.config import ReportGenerationConfig
from src.main import main

if __name__ == "__main__":
    ReportGenerationConfig.mostrar_config()
    sys.exit(main())