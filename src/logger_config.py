"""
Configuración de logging del proyecto.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from .config import LoggingConfig


class LoggerFactory:
    """Factory para crear loggers configurados consistentemente."""
    
    _configured: bool = False
    
    @staticmethod
    def configurar_logging_global() -> None:
        """Configura el sistema de logging global una sola vez."""
        if LoggerFactory._configured:
            return
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        LoggingConfig.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        formatter = logging.Formatter(
            LoggingConfig.LOG_FORMAT,
            datefmt=LoggingConfig.DATE_FORMAT
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        file_handler = logging.handlers.RotatingFileHandler(
            LoggingConfig.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        LoggerFactory._configured = True
    
    @staticmethod
    def obtener_logger(nombre: str) -> logging.Logger:
        """Obtiene un logger configurado para un módulo específico."""
        LoggerFactory.configurar_logging_global()
        return logging.getLogger(nombre)


def obtener_logger(nombre: str) -> logging.Logger:
    """Obtiene un logger configurado."""
    return LoggerFactory.obtener_logger(nombre)