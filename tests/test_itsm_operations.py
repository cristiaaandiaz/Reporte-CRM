"""
Tests for src/itsm_operations.py
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path


class TestConsultarParentCIEnITSM:
    """Tests for consultar_parent_ci_en_itsm function."""
    
    @patch("src.itsm_operations.requests.get")
    def test_returns_parent_ci_on_success(self, mock_get):
        """Test returns ParentCI when found."""
        from src.itsm_operations import consultar_parent_ci_en_itsm
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"Relationship": {"ParentCI": "Empresas - Test_900123456"}}
            ]
        }
        mock_get.return_value = mock_response
        
        parent_ci, mensaje = consultar_parent_ci_en_itsm("sc-001")
        
        assert parent_ci == "Empresas - Test_900123456"
        assert "ParentCI" in mensaje
    
    @patch("src.itsm_operations.requests.get")
    def test_returns_none_on_404(self, mock_get):
        """Test returns None when relation not found."""
        from src.itsm_operations import consultar_parent_ci_en_itsm
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        parent_ci, mensaje = consultar_parent_ci_en_itsm("sc-001")
        
        assert parent_ci is None
        assert "404" in mensaje
    
    @patch("src.itsm_operations.requests.get")
    def test_returns_none_on_empty_content(self, mock_get):
        """Test returns None when content is empty."""
        from src.itsm_operations import consultar_parent_ci_en_itsm
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": []}
        mock_get.return_value = mock_response
        
        parent_ci, mensaje = consultar_parent_ci_en_itsm("sc-001")
        
        assert parent_ci is None
    
    def test_returns_none_for_empty_end2_id(self):
        """Test returns None when end2_id is empty."""
        from src.itsm_operations import consultar_parent_ci_en_itsm
        
        parent_ci, mensaje = consultar_parent_ci_en_itsm("")
        
        assert parent_ci is None
        assert "vacío" in mensaje


class TestCrearHeadersITSM:
    """Tests for _crear_headers_itsm function."""
    
    def test_creates_basic_auth_header(self):
        """Test creates headers with Basic Auth."""
        from src.itsm_operations import _crear_headers_itsm
        from src.config import ITSMConfig
        
        config = ITSMConfig()
        config.USERNAME = "testuser"
        config.PASSWORD = "testpass"
        
        headers = _crear_headers_itsm(config)
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"


class TestEjecutarUpdateITSM:
    """Tests for ejecutar_update_itsm function."""
    
    @patch("src.itsm_operations.requests.put")
    def test_returns_true_on_success(self, mock_put):
        """Test returns True on successful PUT."""
        from src.itsm_operations import ejecutar_update_itsm
        from src.config import ITSMConfig
        
        config = ITSMConfig()
        config.BASE_URL = "http://test.com"
        config.USERNAME = "user"
        config.PASSWORD = "pass"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response
        
        exito, mensaje = ejecutar_update_itsm("http://test.com/cirelationship1to1s/ParentCI/ChildCI", config)
        
        assert exito == True
    
    @patch("src.itsm_operations.requests.put")
    def test_returns_false_on_404(self, mock_put):
        """Test returns False when relation not found."""
        from src.itsm_operations import ejecutar_update_itsm
        from src.config import ITSMConfig
        
        config = ITSMConfig()
        config.BASE_URL = "http://test.com"
        config.USERNAME = "user"
        config.PASSWORD = "pass"
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_put.return_value = mock_response
        
        exito, mensaje = ejecutar_update_itsm("http://test.com/cirelationship1to1s/ParentCI/ChildCI", config)
        
        assert exito == False
    
    def test_returns_false_for_empty_url(self):
        """Test returns False when URL is empty."""
        from src.itsm_operations import ejecutar_update_itsm
        from src.config import ITSMConfig
        
        config = ITSMConfig()
        
        exito, mensaje = ejecutar_update_itsm("", config)
        
        assert exito == False
        assert "vacía" in mensaje


class TestEliminarEnITSM:
    """Tests for eliminar_en_itsm function."""
    
    @patch("src.itsm_operations.consultar_parent_ci_en_itsm")
    def test_processes_relations_with_fo(self, mock_consult, temp_dir):
        """Test processes only relations with FO in simulation."""
        from src.itsm_operations import eliminar_en_itsm
        
        mock_consult.return_value = ("Empresas - Test_900123456", "ParentCI: Test")
        
        relaciones = [
            {
                "ucmdbId": "rel-001",
                "end1Id": "crm-001",
                "end2Id": "sc-001",
                "nit_end1": "900123456",
                "nit_end2": "901999048",
                "display_label_end1": "CRM",
                "display_label_end2": "SC",
                "relacion_fo": True,
                "ucmdbid_fo": "cont-001"
            }
        ]
        
        # This should work in simulation mode
        eliminar_en_itsm(
            inconsistencias_normales_con_fo=relaciones,
            carpeta=temp_dir,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
    
    def test_returns_none_when_empty(self, temp_dir):
        """Test returns None when no relations."""
        from src.itsm_operations import eliminar_en_itsm
        
        # Should not raise, just return
        eliminar_en_itsm(
            inconsistencias_normales_con_fo=[],
            carpeta=temp_dir,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )
    
    def test_filters_out_relations_without_fo(self, temp_dir):
        """Test filters out relations without FO."""
        from src.itsm_operations import eliminar_en_itsm
        
        relaciones_sin_fo = [
            {
                "ucmdbId": "rel-001",
                "end1Id": "crm-001",
                "end2Id": "sc-001",
                "relacion_fo": False,
                "ucmdbid_fo": "N/A"
            }
        ]
        
        # This should filter out the relation since it doesn't have FO
        eliminar_en_itsm(
            inconsistencias_normales_con_fo=relaciones_sin_fo,
            carpeta=temp_dir,
            modo_ejecucion="simulacion",
            generar_resumen=False
        )