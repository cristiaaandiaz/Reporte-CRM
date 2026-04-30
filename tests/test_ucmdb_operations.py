"""
Tests for src/ucmdb_operations.py
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path


class TestEjecutarDeleteUCMDB:
    """Tests for ejecutar_delete_ucmdb function."""
    
    @patch("src.ucmdb_operations.requests.delete")
    def test_returns_true_on_success(self, mock_delete, mock_ucmdb_config):
        """Test returns True on successful DELETE."""
        from src.ucmdb_operations import ejecutar_delete_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        exito, mensaje = ejecutar_delete_ucmdb("http://test.com/rel-001", "token", mock_ucmdb_config)
        
        assert exito == True
        assert "204" in mensaje
    
    @patch("src.ucmdb_operations.requests.delete")
    def test_returns_false_on_404(self, mock_delete, mock_ucmdb_config):
        """Test returns False when relation not found."""
        from src.ucmdb_operations import ejecutar_delete_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response
        
        exito, mensaje = ejecutar_delete_ucmdb("http://test.com/rel-001", "token", mock_ucmdb_config)
        
        assert exito == False
        assert "404" in mensaje
    
    @patch("src.ucmdb_operations.requests.delete")
    def test_returns_false_on_server_error(self, mock_delete, mock_ucmdb_config):
        """Test returns False on server error."""
        from src.ucmdb_operations import ejecutar_delete_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_delete.return_value = mock_response
        
        # Exhaust all retries
        exito, mensaje = ejecutar_delete_ucmdb("http://test.com/rel-001", "token", mock_ucmdb_config, max_reintentos=1, delay_reintento=0)
        
        assert exito == False


class TestEliminarEnUCMDB:
    """Tests for eliminar_en_ucmdb function."""
    
    @patch("src.ucmdb_operations.ejecutar_delete_ucmdb")
    def test_processes_inconsistencies(self, mock_delete, mock_ucmdb_config):
        """Test processes all inconsistencies in simulation mode."""
        from src.ucmdb_operations import eliminar_en_ucmdb
        
        mock_delete.return_value = (True, "Eliminado")
        
        inconsistencias = [
            {
                "ucmdbId": "rel-001",
                "nit_end1": "900123456",
                "nit_end2": "901999048",
                "end1Id": "crm-001",
                "end2Id": "sc-001",
                "display_label_end1": "CRM",
                "display_label_end2": "SC",
                "relacion_fo": False,
                "ucmdbid_fo": "N/A"
            }
        ]
        
        result = eliminar_en_ucmdb(
            token="test_token",
            inconsistencias=inconsistencias,
            carpeta=Path("reports/test"),
            config=mock_ucmdb_config,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
        
        assert result is not None
        assert len(result) == 1
    
    @patch("src.ucmdb_operations.ejecutar_delete_ucmdb")
    def test_deletes_fo_relation_too(self, mock_delete, mock_ucmdb_config):
        """Test also deletes FO relation when relacion_fo is True."""
        from src.ucmdb_operations import eliminar_en_ucmdb
        
        mock_delete.return_value = (True, "Eliminado")
        
        inconsistencias = [
            {
                "ucmdbId": "rel-001",
                "nit_end1": "900123456",
                "nit_end2": "901999048",
                "end1Id": "crm-001",
                "end2Id": "sc-001",
                "display_label_end1": "CRM",
                "display_label_end2": "SC",
                "relacion_fo": True,
                "ucmdbid_fo": "cont-001"
            }
        ]
        
        result = eliminar_en_ucmdb(
            token="test_token",
            inconsistencias=inconsistencias,
            carpeta=Path("reports/test"),
            config=mock_ucmdb_config,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
        
        # Should have 2 deletes: main relation + FO
        assert len(result) == 2
    
    def test_returns_none_when_empty(self, mock_ucmdb_config):
        """Test returns None when no inconsistencies."""
        from src.ucmdb_operations import eliminar_en_ucmdb
        
        result = eliminar_en_ucmdb(
            token="test_token",
            inconsistencias=[],
            carpeta=Path("reports/test"),
            config=mock_ucmdb_config,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
        
        assert result is None


class TestEliminarRelacionesUsageDeServicecodes:
    """Tests for eliminar_relaciones_usage_de_servicecodes function."""
    
    @patch("src.ucmdb_operations.ejecutar_delete_ucmdb")
    def test_processes_usage_relations(self, mock_delete, mock_ucmdb_config):
        """Test processes usage relations in simulation mode."""
        from src.ucmdb_operations import eliminar_relaciones_usage_de_servicecodes
        
        mock_delete.return_value = (True, "Eliminado")
        
        relaciones_usage = [
            {
                "ucmdbId": "usage-001",
                "end1Id": "app-001",
                "end2Id": "sc-001",
                "type": "usage",
                "display_label_end1": "App",
                "display_label_end2": "ServiceCode"
            }
        ]
        
        result = eliminar_relaciones_usage_de_servicecodes(
            token="test_token",
            relaciones_usage=relaciones_usage,
            carpeta=Path("reports/test"),
            config=mock_ucmdb_config,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
        
        assert result is not None
        assert len(result) == 1
    
    def test_returns_none_when_empty(self, mock_ucmdb_config):
        """Test returns None when no usage relations."""
        from src.ucmdb_operations import eliminar_relaciones_usage_de_servicecodes
        
        result = eliminar_relaciones_usage_de_servicecodes(
            token="test_token",
            relaciones_usage=[],
            carpeta=Path("reports/test"),
            config=mock_ucmdb_config,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
        
        assert result is None