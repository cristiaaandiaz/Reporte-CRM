"""
Tests for src/config.py
"""

import pytest
import os
from pathlib import Path


class TestExecutionFlags:
    """Tests for ExecutionFlags class."""
    
    def test_default_values(self):
        """Test default values are correct."""
        from src.config import ExecutionFlags
        assert ExecutionFlags.MODO_EJECUCION == "simulacion"
        assert ExecutionFlags.USAR_REPORTE_LOCAL == False
        assert ExecutionFlags.CREAR_CARPETA_EJECUCION == True
    
    def test_validar_simulacion(self):
        """Test validation with valid mode."""
        from src.config import ExecutionFlags
        ExecutionFlags.MODO_EJECUCION = "simulacion"
        # Should not raise
        ExecutionFlags.validar()
    
    def test_validar_ejecucion(self):
        """Test validation with ejecucion mode."""
        from src.config import ExecutionFlags
        ExecutionFlags.MODO_EJECUCION = "ejecucion"
        ExecutionFlags.validar()
    
    def test_validar_invalid_mode_raises(self):
        """Test that invalid mode raises ValueError."""
        from src.config import ExecutionFlags
        ExecutionFlags.MODO_EJECUCION = "invalid"
        with pytest.raises(ValueError):
            ExecutionFlags.validar()


class TestReportGenerationConfig:
    """Tests for ReportGenerationConfig class."""
    
    def test_default_values(self):
        """Test default report generation flags."""
        from src.config import ReportGenerationConfig
        assert ReportGenerationConfig.REPORTE_JSON == True
        assert ReportGenerationConfig.INCONSISTENCIAS == True
        assert ReportGenerationConfig.RESUMEN_UCMDB == True
        assert ReportGenerationConfig.RESUMEN_ITSM == True
    
    def test_obtener_resumen_config(self):
        """Test config summary returns correct dict."""
        from src.config import ReportGenerationConfig
        summary = ReportGenerationConfig.obtener_resumen_config()
        assert isinstance(summary, dict)
        assert "reporte_json" in summary
        assert "inconsistencias" in summary


class TestUCMDBConfig:
    """Tests for UCMDBConfig dataclass."""
    
    def test_default_values(self):
        """Test default UCMDB config values."""
        from src.config import UCMDBConfig
        config = UCMDBConfig()
        assert config.TARGET_NODE_TYPE == "clr_onyxservicecodes"
        assert config.NIT_FIELD_END1 == "clr_onyxdb_company_nit"
        assert config.NIT_FIELD_END2 == "clr_onyxdb_companynit"
        assert config.CONNECT_TIMEOUT == 60
        assert config.READ_TIMEOUT == 3600
    
    def test_validar_raises_without_credentials(self):
        """Test validation raises when credentials are missing."""
        from src.config import UCMDBConfig
        config = UCMDBConfig()
        config.USERNAME = ""
        config.PASSWORD = ""
        with pytest.raises(ValueError):
            config.validar()
    
    def test_validar_passes_with_credentials(self):
        """Test validation passes with credentials."""
        from src.config import UCMDBConfig
        config = UCMDBConfig()
        config.USERNAME = "test"
        config.PASSWORD = "test"
        # Should not raise
        config.validar()


class TestITSMConfig:
    """Tests for ITSMConfig dataclass."""
    
    def test_default_values(self):
        """Test default ITSM config values."""
        from src.config import ITSMConfig
        config = ITSMConfig()
        assert config.TIMEOUT == 30
        assert config.MAX_RETRIES == 3
        assert config.RETRY_DELAY == 2
    
    def test_validar_raises_without_credentials(self):
        """Test validation raises when ITSM config is incomplete."""
        from src.config import ITSMConfig
        config = ITSMConfig()
        config.BASE_URL = ""
        config.USERNAME = ""
        config.PASSWORD = ""
        with pytest.raises(ValueError):
            config.validar()


class TestLoggingConfig:
    """Tests for LoggingConfig class."""
    
    def test_default_values(self):
        """Test default logging config."""
        from src.config import LoggingConfig
        assert LoggingConfig.LOG_LEVEL == "INFO"
        assert LoggingConfig.LOG_FORMAT == "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        assert LoggingConfig.DATE_FORMAT == "%Y-%m-%d %H:%M:%S"


class TestExitCodes:
    """Tests for ExitCodes class."""
    
    def test_exit_codes_values(self):
        """Test exit code values."""
        from src.config import ExitCodes
        assert ExitCodes.SUCCESS == 0
        assert ExitCodes.AUTH_ERROR == 1
        assert ExitCodes.REPORT_ERROR == 2
        assert ExitCodes.JSON_ERROR == 3
        assert ExitCodes.CONFIG_ERROR == 4
        assert ExitCodes.EXECUTION_ERROR == 5