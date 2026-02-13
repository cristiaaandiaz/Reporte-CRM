"""
Módulo de Configuración Centralizada.

Este módulo centraliza toda la configuración del proyecto,
incluyendo URLs, timeouts, y comportamientos de ejecución.
Todas las variables se cargan desde el archivo .env o valores por defecto.
"""

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv


# Cargar variables de entorno
load_dotenv()


# ==================== RUTAS BASE ====================
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_BASE_DIR = PROJECT_ROOT / "reports"
LOGS_BASE_DIR = PROJECT_ROOT / "logs"

# Crear directorios si no existen
REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_BASE_DIR.mkdir(parents=True, exist_ok=True)


# ==================== FLAGS DE CONTROL ====================
class ExecutionFlags:
    """
    Controla el comportamiento de ejecución del script.
    
    Attributes:
        MODO_EJECUCION: "simulacion" (DRY-RUN) o "ejecucion" (eliminaciones REALES)
        USAR_REPORTE_LOCAL: True para usar JSON local, False para traer de API
        GENERAR_RESUMEN: True para generar archivos de resumen
        CREAR_CARPETA_EJECUCION: True para crear carpeta con timestamp
    """
    
    # Modo de ejecución para AMBAS APIs (UCMDB + ITSM)
    # "simulacion" => DRY-RUN (recomendado primero)
    # "ejecucion" => Eliminaciones REALES en producción
    MODO_EJECUCION = "simulacion"
    
    # True = Usar JSON local para pruebas (no llama API UCMDB)
    # False = Traer reporte de la API UCMDB (producción)
    USAR_REPORTE_LOCAL = False
    
    # Generación de reportes y carpetas
    GENERAR_RESUMEN = True
    CREAR_CARPETA_EJECUCION = True
    
    @staticmethod
    def validar():
        """Valida que los flags estén en valores válidos."""
        if ExecutionFlags.MODO_EJECUCION not in ["simulacion", "ejecucion"]:
            raise ValueError(
                f"MODO_EJECUCION debe ser 'simulacion' o 'ejecucion', "
                f"no '{ExecutionFlags.MODO_EJECUCION}'"
            )


# ==================== CONFIGURACIÓN REPORTE LOCAL ====================
class ReportConfig:
    """Configuración para lectura de reportes."""
    
    # Ruta del reporte JSON local para pruebas/debug
    RUTA_REPORTE_LOCAL = REPORTS_BASE_DIR / "reporte_test.json"
    
    # Nombre del reporte en UCMDB
    REPORT_NAME = "Reporte_Clientes_Onyx-uCMDB"


# ==================== CONFIGURACIÓN UCMDB ====================
@dataclass
class UCMDBConfig:
    """Configuración para conexión con UCMDB."""
    
    # URLs base
    AUTH_URL: str = "https://ucmdbapp.triara.co:8443/rest-api/authenticate"
    BASE_URL: str = "https://ucmdbapp.triara.co:8443/rest-api/topology"
    DELETE_ENDPOINT: str = "https://ucmdbapp.triara.co:8443/rest-api/dataModel/relation"
    
    # Timeouts
    CONNECT_TIMEOUT: int = 60  # Aumentado para conexión lenta
    READ_TIMEOUT: int = 3600   # 1 HORA para descargas de 250+ MB
    REQUEST_TIMEOUT: int = 30
    
    # Reintentos
    MAX_RETRIES: int = 5
    RETRY_DELAY: int = 15  # segundos entre reintentos
    
    # Credenciales (se cargan de .env)
    USERNAME: str = os.getenv("UCMDB_USER", "")
    PASSWORD: str = os.getenv("UCMDB_PASS", "")
    
    # Campos y tipos
    TARGET_NODE_TYPE: str = "clr_onyxservicecodes"
    NIT_FIELD_END1: str = "clr_onyxdb_company_nit"
    NIT_FIELD_END2: str = "clr_onyxdb_companynit"
    CONTENT_TYPE: str = "text/plain"
    
    # Cliente
    CLIENT_CONTEXT: int = 1
    
    def validar(self):
        """Valida que las credenciales estén configuradas."""
        if not self.USERNAME or not self.PASSWORD:
            raise ValueError(
                "ERROR CRÍTICO: Credenciales UCMDB faltantes en .env\n"
                "  Requeridas: UCMDB_USER, UCMDB_PASS"
            )


# ==================== CONFIGURACIÓN ITSM ====================
@dataclass
class ITSMConfig:
    """Configuración para conexión con ITSM."""
    
    # URLs base
    BASE_URL: str = os.getenv("ITSM_URL", "")
    
    # Credenciales
    USERNAME: str = os.getenv("ITSM_USERNAME", "")
    PASSWORD: str = os.getenv("ITSM_PASSWORD", "")
    
    # Timeouts y reintentos
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    
    # Endpoint relativo
    ENDPOINT_PATTERN: str = "/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}"
    
    def validar(self):
        """Valida que la configuración ITSM esté completa."""
        if not all([self.BASE_URL, self.USERNAME, self.PASSWORD]):
            raise ValueError(
                "ERROR CRÍTICO: Credenciales ITSM faltantes en .env\n"
                "  Requeridas: ITSM_URL, ITSM_USERNAME, ITSM_PASSWORD"
            )


# ==================== CONFIGURACIÓN LOGGING ====================
class LoggingConfig:
    """Configuración para el sistema de logging."""
    
    # Nivel de logging
    LOG_LEVEL = "INFO"
    
    # Archivos de log
    LOG_FILE = LOGS_BASE_DIR / "ucmdb_validation.log"
    
    # Formato
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Archivos separados por componente
    UCMDB_LOG_FILE = LOGS_BASE_DIR / "ucmdb.log"
    ITSM_LOG_FILE = LOGS_BASE_DIR / "itsm.log"
    AUTH_LOG_FILE = LOGS_BASE_DIR / "auth.log"


# ==================== CÓDIGOS DE SALIDA ====================
class ExitCodes:
    """Códigos de salida estándar del script."""
    
    SUCCESS = 0
    AUTH_ERROR = 1
    REPORT_ERROR = 2
    JSON_ERROR = 3
    CONFIG_ERROR = 4
    EXECUTION_ERROR = 5


# ==================== INSTANCIAS GLOBALES ====================
# Se crean instancias para acceso fácil en todo el código
ucmdb_config = UCMDBConfig()
itsm_config = ITSMConfig()


def validar_configuracion_inicial():
    """
    Valida que toda la configuración sea válida antes de ejecutar.
    
    Raises:
        ValueError: Si hay errores en la configuración.
    """
    ExecutionFlags.validar()
    ucmdb_config.validar()
    itsm_config.validar()
