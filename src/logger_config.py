"""
Módulo de Configuración Centralizada de Logging.

Proporciona funciones para configurar el sistema de logging
de manera consistente en todo el proyecto.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from .config import LoggingConfig


class LoggerFactory:
    """
    Factory para crear loggers configurados profesionalmente.
    
    Asegura que todos los loggers del proyecto tengan una configuración
    consistente.
    """
    
    _configured = False
    
    @staticmethod
    def configurar_logging_global():
        """Configura el sistema de logging global una sola vez."""
        if LoggerFactory._configured:
            return
        
        # Obtener logger raíz
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Crear carpeta de logs si no existe
        LoggingConfig.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Formato
        formatter = logging.Formatter(
            LoggingConfig.LOG_FORMAT,
            datefmt=LoggingConfig.DATE_FORMAT
        )
        
        # Handler para stdout (consola)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Handler para archivo (main log)
        file_handler = logging.handlers.RotatingFileHandler(
            LoggingConfig.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Agregar handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        
        LoggerFactory._configured = True
    
    @staticmethod
    def obtener_logger(nombre: str) -> logging.Logger:
        """
        Obtiene un logger configurado para un módulo específico.
        
        Args:
            nombre: Nombre del logger (típicamente __name__)
            
        Returns:
            logging.Logger: Logger configurado y listo para usar
        """
        LoggerFactory.configurar_logging_global()
        return logging.getLogger(nombre)


# Función de conveniencia global
def obtener_logger(nombre: str) -> logging.Logger:
    """
    Obtiene un logger configurado.
    
    Args:
        nombre: Nombre del logger (típicamente __name__)
        
    Returns:
        logging.Logger: Logger configurado
    """
    return LoggerFactory.obtener_logger(nombre)
