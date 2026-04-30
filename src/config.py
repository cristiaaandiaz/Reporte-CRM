"""
Configuración centralizada del proyecto.
Carga variables desde .env y define URLs, timeouts y comportamientos de ejecución.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_BASE_DIR = PROJECT_ROOT / "reports"
LOGS_BASE_DIR = PROJECT_ROOT / "logs"

REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_BASE_DIR.mkdir(parents=True, exist_ok=True)


class ExecutionFlags:
    """Controla el comportamiento de ejecución."""
    
    MODO_EJECUCION: str = "simulacion"  # "simulacion" o "ejecucion"
    USAR_REPORTE_LOCAL: bool = False
    CREAR_CARPETA_EJECUCION: bool = True
    
    @staticmethod
    def validar() -> None:
        if ExecutionFlags.MODO_EJECUCION not in ["simulacion", "ejecucion"]:
            raise ValueError(f"MODO_EJECUCION debe ser 'simulacion' o 'ejecucion'")


class ReportGenerationConfig:
    """Permite parametrizar qué archivos de reportes se generan."""
    
    REPORTE_JSON: bool = True
    INCONSISTENCIAS: bool = True
    RESUMEN_UCMDB: bool = True
    RESUMEN_ITSM: bool = True
    
    @staticmethod
    def obtener_resumen_config() -> dict[str, bool]:
        return {
            "reporte_json": ReportGenerationConfig.REPORTE_JSON,
            "inconsistencias": ReportGenerationConfig.INCONSISTENCIAS,
            "resumen_ucmdb": ReportGenerationConfig.RESUMEN_UCMDB,
            "resumen_itsm": ReportGenerationConfig.RESUMEN_ITSM,
        }
    
    @staticmethod
    def mostrar_config() -> None:
        print("\n" + "=" * 80)
        print("CONFIGURACIÓN DE GENERACIÓN DE REPORTES")
        print("=" * 80)
        config = ReportGenerationConfig.obtener_resumen_config()
        for nombre, habilitado in config.items():
            estado = "[ON]  HABILITADO" if habilitado else "[OFF] DESHABILITADO"
            print(f"  {nombre.upper():40} {estado}")
        print("=" * 80 + "\n")


class ReportConfig:
    """Configuración para lectura de reportes."""
    
    RUTA_REPORTE_LOCAL: Path = REPORTS_BASE_DIR / "reporte.json"
    REPORT_NAME: str = "Reporte_Clientes_Onyx-uCMDB"


@dataclass
class UCMDBConfig:
    """Configuración para conexión con UCMDB."""
    
    AUTH_URL: str = "https://ucmdbapp.triara.co:8443/rest-api/authenticate"
    BASE_URL: str = "https://ucmdbapp.triara.co:8443/rest-api/topology"
    DELETE_ENDPOINT: str = "https://ucmdbapp.triara.co:8443/rest-api/dataModel/relation"
    
    CONNECT_TIMEOUT: int = 60
    READ_TIMEOUT: int = 3600
    REQUEST_TIMEOUT: int = 30
    
    MAX_RETRIES: int = 5
    RETRY_DELAY: int = 15
    
    USERNAME: str = os.getenv("UCMDB_USER", "")
    PASSWORD: str = os.getenv("UCMDB_PASS", "")
    
    TARGET_NODE_TYPE: str = "clr_onyxservicecodes"
    NIT_FIELD_END1: str = "clr_onyxdb_company_nit"
    NIT_FIELD_END2: str = "clr_onyxdb_companynit"
    CONTENT_TYPE: str = "text/plain"
    
    CLIENT_CONTEXT: int = 1
    
    def validar(self) -> None:
        if not self.USERNAME or not self.PASSWORD:
            raise ValueError("Credenciales UCMDB faltantes en .env: UCMDB_USER, UCMDB_PASS")


VERIFY_SSL: bool = os.getenv("VERIFY_SSL", "False").lower() == "true"

if not VERIFY_SSL:
    import warnings
    warnings.warn(
        "⚠️ ADVERTENCIA: VERIFY_SSL=False. Usar True en producción.",
        category=Warning,
        stacklevel=2
    )


@dataclass
class ITSMConfig:
    """Configuración para conexión con ITSM."""
    
    BASE_URL: str = os.getenv("ITSM_URL", "")
    USERNAME: str = os.getenv("ITSM_USERNAME", "")
    PASSWORD: str = os.getenv("ITSM_PASSWORD", "")
    
    TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 2
    
    ENDPOINT_PATTERN: str = "/cirelationship1to1s/{ucmdbid_fo}/{ucmdbid}"
    
    def validar(self) -> None:
        if not all([self.BASE_URL, self.USERNAME, self.PASSWORD]):
            raise ValueError("Credenciales ITSM faltantes en .env: ITSM_URL, ITSM_USERNAME, ITSM_PASSWORD")


class LoggingConfig:
    """Configuración para el sistema de logging."""
    
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Path = LOGS_BASE_DIR / "ucmdb_validation.log"
    LOG_FORMAT: str = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    UCMDB_LOG_FILE: Path = LOGS_BASE_DIR / "ucmdb.log"
    ITSM_LOG_FILE: Path = LOGS_BASE_DIR / "itsm.log"
    AUTH_LOG_FILE: Path = LOGS_BASE_DIR / "auth.log"


class ExitCodes:
    """Códigos de salida estándar del script."""
    
    SUCCESS: int = 0
    AUTH_ERROR: int = 1
    REPORT_ERROR: int = 2
    JSON_ERROR: int = 3
    CONFIG_ERROR: int = 4
    EXECUTION_ERROR: int = 5


ucmdb_config: UCMDBConfig = UCMDBConfig()
itsm_config: ITSMConfig = ITSMConfig()


def validar_configuracion_inicial() -> None:
    """Valida que toda la configuración sea válida antes de ejecutar."""
    ExecutionFlags.validar()
    ucmdb_config.validar()
    itsm_config.validar()