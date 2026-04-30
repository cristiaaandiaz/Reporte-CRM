"""
Tests for src/processor.py
"""

import pytest
from pathlib import Path
import json
from unittest.mock import patch, MagicMock


class TestGuardarReporteJSON:
    """Tests for guardar_reporte_json function."""
    
    def test_saves_json_file(self, temp_dir, sample_json_data):
        """Test saves JSON file to disk."""
        from src.processor import guardar_reporte_json
        
        result = guardar_reporte_json(sample_json_data, temp_dir)
        
        assert result is not None
        assert result.exists()
        assert result.suffix == ".json"
    
    def test_returns_none_when_disabled(self, temp_dir):
        """Test returns None when folder name is disabled."""
        from src.processor import guardar_reporte_json
        
        disabled_path = Path(str(temp_dir) + "/disabled")
        result = guardar_reporte_json({}, disabled_path)
        
        assert result is None


class TestGuardarInconsistenciasDetalle:
    """Tests for guardar_inconsistencias_detalle function."""
    
    def test_saves_inconsistencies_file(self, temp_dir):
        """Test saves inconsistencies to file."""
        from src.processor import guardar_inconsistencias_detalle
        
        inconsistencias = [
            {
                "ucmdbId": "rel-001",
                "nit_end1": "900123456",
                "nit_end2": "901999048",
                "end1Id": "crm-001",
                "end2Id": "sc-001",
                "display_label_end1": "CRM",
                "display_label_end2": "ServiceCode",
                "relacion_fo": True,
                "ucmdbid_fo": "fo-001"
            }
        ]
        
        result = guardar_inconsistencias_detalle(inconsistencias, temp_dir, "inconsistencias.txt")
        
        assert result is not None
        assert result.exists()
        assert "inconsistencias.txt" in str(result)
    
    def test_returns_none_when_empty(self, temp_dir):
        """Test returns None when inconsistencies list is empty."""
        from src.processor import guardar_inconsistencias_detalle
        
        result = guardar_inconsistencias_detalle([], temp_dir, "test.txt")
        
        assert result is None


class TestEnriquecerInconsistenciasNormales:
    """Tests for enriquecer_inconsistencias_normales function."""
    
    def test_adds_fo_info_when_containment_exists(self):
        """Test adds FO info when containment relation exists."""
        from src.processor import enriquecer_inconsistencias_normales
        
        inconsistencias = [
            {"ucmdbId": "rel-001", "nit_end1": "A", "nit_end2": "B", "end1Id": "crm-001", "end2Id": "sc-001"}
        ]
        
        relations = [
            {"ucmdbId": "rel-001", "end2Id": "sc-001"},
            {"ucmdbId": "cont-001", "type": "containment", "end1Id": "fo-001", "end2Id": "sc-001"}
        ]
        
        containment_by_end2 = {"sc-001": {"ucmdbId": "cont-001", "end1Id": "fo-001"}}
        cis_by_id = {"fo-001": {"type": "clr_service_catalog_fo_e"}}
        
        result = enriquecer_inconsistencias_normales(inconsistencias, relations, containment_by_end2, cis_by_id)
        
        assert result[0]["relacion_fo"] == True
        assert result[0]["ucmdbid_fo"] == "cont-001"
    
    def test_keeps_fo_false_when_no_containment(self):
        """Test keeps FO false when no containment exists."""
        from src.processor import enriquecer_inconsistencias_normales
        
        inconsistencias = [
            {"ucmdbId": "rel-001", "nit_end1": "A", "nit_end2": "B", "end1Id": "crm-001", "end2Id": "sc-001"}
        ]
        
        relations = [
            {"ucmdbId": "rel-001", "end2Id": "sc-001"}
        ]
        
        containment_by_end2 = {}
        cis_by_id = {}
        
        result = enriquecer_inconsistencias_normales(inconsistencias, relations, containment_by_end2, cis_by_id)
        
        assert result[0]["relacion_fo"] == False
        assert result[0]["ucmdbid_fo"] == "N/A"


class TestCrearDirectorioEjecucion:
    """Tests for crear_directorio_ejecucion function."""
    
    def test_creates_directory_with_timestamp(self):
        """Test creates directory with timestamp."""
        from src.processor import crear_directorio_ejecucion
        
        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(Path(__file__).parent.parent)
            result = crear_directorio_ejecucion(True)
            
            assert result.exists()
            assert "ejecucion_" in str(result)
    
    def test_returns_disabled_when_flag_false(self):
        """Test returns disabled path when flag is False."""
        from src.processor import crear_directorio_ejecucion
        
        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(Path(__file__).parent.parent)
            result = crear_directorio_ejecucion(False)
            
            assert "disabled" in str(result)


class TestValidarIntegridadJSON:
    """Tests for validar_integridad_json function."""
    
    def test_returns_true_for_valid_json(self, sample_json_data):
        """Test returns True for valid JSON."""
        from src.processor import validar_integridad_json
        
        result = validar_integridad_json(sample_json_data)
        assert result == True
    
    def test_returns_false_for_empty_cis(self):
        """Test returns False when cis list is empty."""
        from src.processor import validar_integridad_json
        
        data = {"cis": [], "relations": [{"ucmdbId": "rel-001"}]}
        result = validar_integridad_json(data)
        assert result == False
    
    def test_returns_false_for_empty_relations(self):
        """Test returns False when relations list is empty."""
        from src.processor import validar_integridad_json
        
        data = {"cis": [{"ucmdbId": "ci-001"}], "relations": []}
        result = validar_integridad_json(data)
        assert result == False
    
    def test_returns_false_for_missing_cis_key(self):
        """Test returns False when cis key is missing."""
        from src.processor import validar_integridad_json
        
        data = {"relations": [{"ucmdbId": "rel-001"}]}
        result = validar_integridad_json(data)
        assert result == False


class TestGuardarRelacionesUsageDetalle:
    """Tests for guardar_relaciones_usage_detalle function."""
    
    def test_saves_usage_relations(self, temp_dir):
        """Test saves usage relations to file."""
        from src.processor import guardar_relaciones_usage_detalle
        
        relaciones = [
            {
                "ucmdbId": "usage-001",
                "end1Id": "app-001",
                "end2Id": "sc-001",
                "type": "usage",
                "display_label_end1": "App",
                "display_label_end2": "ServiceCode",
                "ci_type_end1": "business_application",
                "ci_type_end2": "clr_onyxservicecodes"
            }
        ]
        
        result = guardar_relaciones_usage_detalle(relaciones, temp_dir, "usage_test.txt")
        
        assert result is not None
        assert result.exists()
    
    def test_returns_none_when_empty(self, temp_dir):
        """Test returns None when list is empty."""
        from src.processor import guardar_relaciones_usage_detalle
        
        result = guardar_relaciones_usage_detalle([], temp_dir, "test.txt")
        assert result is None