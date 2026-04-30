"""
Tests for src/report.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO


class TestHTTPAdapterWithSocketKeepalive:
    """Tests for HTTPAdapterWithSocketKeepalive class."""
    
    def test_adapter_created(self):
        """Test adapter can be created."""
        from src.report import HTTPAdapterWithSocketKeepalive
        adapter = HTTPAdapterWithSocketKeepalive()
        assert adapter is not None


class TestFiltrarCIsPorTipoServicecodes:
    """Tests for filtrar_cis_por_tipo_servicecodes function."""
    
    def test_filters_servicecodes(self, sample_json_data, mock_ucmdb_config):
        """Test filters only servicecodes from CIs."""
        from src.report import filtrar_cis_por_tipo_servicecodes
        
        result = filtrar_cis_por_tipo_servicecodes(sample_json_data, mock_ucmdb_config)
        
        assert len(result) == 2
        for ci in result:
            assert ci["type"] == "clr_onyxservicecodes"
    
    def test_returns_empty_list_for_invalid_data(self, mock_ucmdb_config):
        """Test returns empty list for invalid JSON data."""
        from src.report import filtrar_cis_por_tipo_servicecodes
        
        result = filtrar_cis_por_tipo_servicecodes({}, mock_ucmdb_config)
        assert result == []
    
    def test_returns_empty_list_when_no_cis(self, mock_ucmdb_config):
        """Test returns empty list when no CIs."""
        from src.report import filtrar_cis_por_tipo_servicecodes
        
        result = filtrar_cis_por_tipo_servicecodes({"cis": []}, mock_ucmdb_config)
        assert result == []


class TestValidarNITEnRelacionesInvertidas:
    """Tests for validar_nit_en_relaciones_invertidas function."""
    
    def test_finds_inconsistent_nits(self, sample_json_data, mock_ucmdb_config):
        """Test finds relationships with different NITs."""
        from src.report import validar_nit_en_relaciones_invertidas
        
        normales, particulares = validar_nit_en_relaciones_invertidas(sample_json_data, mock_ucmdb_config)
        
        # rel-001 has NIT mismatch (900123456 != 901999048)
        # rel-002 has same NIT (900123456 == 900123456) - no inconsistency
        assert len(normales) == 1
        assert normales[0]["nit_end1"] == "900123456"
        assert normales[0]["nit_end2"] == "901999048"
    
    def test_returns_empty_when_no_relations(self, mock_ucmdb_config):
        """Test returns empty lists when no relations."""
        from src.report import validar_nit_en_relaciones_invertidas
        
        normales, particulares = validar_nit_en_relaciones_invertidas({"cis": [], "relations": []}, mock_ucmdb_config)
        
        assert normales == []
        assert particulares == []
    
    def test_returns_empty_for_invalid_data(self, mock_ucmdb_config):
        """Test returns empty for invalid data."""
        from src.report import validar_nit_en_relaciones_invertidas
        
        normales, particulares = validar_nit_en_relaciones_invertidas("invalid", mock_ucmdb_config)
        
        assert normales == []
        assert particulares == []


class TestValidarRelacionesUsageDeServicecodes:
    """Tests for validar_relaciones_usage_de_servicecodes function."""
    
    def test_finds_usage_relations(self, sample_json_data, mock_ucmdb_config):
        """Test finds usage relations to servicecodes."""
        from src.report import validar_relaciones_usage_de_servicecodes
        
        result = validar_relaciones_usage_de_servicecodes(sample_json_data, mock_ucmdb_config)
        
        # usage-001 connects app-001 (business_application) to sc-001
        assert len(result) == 1
        assert result[0]["ucmdbId"] == "usage-001"
        assert result[0]["type"] == "usage"
        assert result[0]["ci_type_end1"] == "business_application"
    
    def test_returns_empty_when_no_usage_relations(self, mock_ucmdb_config):
        """Test returns empty when no usage relations."""
        from src.report import validar_relaciones_usage_de_servicecodes
        
        data = {
            "cis": [{"ucmdbId": "sc-001", "type": "clr_onyxservicecodes", "properties": {}}],
            "relations": []
        }
        
        result = validar_relaciones_usage_de_servicecodes(data, mock_ucmdb_config)
        assert result == []
    
    def test_returns_empty_for_invalid_data(self, mock_ucmdb_config):
        """Test returns empty for invalid data."""
        from src.report import validar_relaciones_usage_de_servicecodes
        
        result = validar_relaciones_usage_de_servicecodes({}, mock_ucmdb_config)
        assert result == []
    
    def test_filters_out_non_business_application(self, mock_ucmdb_config):
        """Test filters out usage where end1 is not business_application."""
        from src.report import validar_relaciones_usage_de_servicecodes
        
        data = {
            "cis": [
                {"ucmdbId": "sc-001", "type": "clr_onyxservicecodes", "properties": {"display_label": "SC1"}},
                {"ucmdbId": "server-001", "type": "server", "properties": {"display_label": "Server"}}
            ],
            "relations": [
                {"ucmdbId": "usage-001", "type": "usage", "end1Id": "server-001", "end2Id": "sc-001"}
            ]
        }
        
        result = validar_relaciones_usage_de_servicecodes(data, mock_ucmdb_config)
        assert result == []  # Filtered out because end1 is not business_application