"""
Pytest configuration and fixtures for tests.
"""

import pytest
from pathlib import Path
import json
import tempfile
import os


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_json_data():
    """Provides sample JSON data for testing."""
    return {
        "cis": [
            {
                "ucmdbId": "crm-001",
                "type": "clr_onyxcrm",
                "properties": {
                    "display_label": "CRM Empresas",
                    "clr_onyxdb_company_nit": "900123456"
                }
            },
            {
                "ucmdbId": "sc-001",
                "type": "clr_onyxservicecodes",
                "properties": {
                    "display_label": "SDWAN - 901999048",
                    "clr_onyxdb_companynit": "901999048"
                }
            },
            {
                "ucmdbId": "sc-002",
                "type": "clr_onyxservicecodes",
                "properties": {
                    "display_label": "Internet - 900123456",
                    "clr_onyxdb_companynit": "900123456"
                }
            },
            {
                "ucmdbId": "app-001",
                "type": "business_application",
                "properties": {
                    "display_label": "Aplicación Principal"
                }
            },
            {
                "ucmdbId": "fo-e-001",
                "type": "clr_service_catalog_fo_e",
                "properties": {
                    "display_label": "FO Enterprise"
                }
            }
        ],
        "relations": [
            {
                "ucmdbId": "rel-001",
                "type": "ownership",
                "end1Id": "crm-001",
                "end2Id": "sc-001"
            },
            {
                "ucmdbId": "rel-002",
                "type": "ownership",
                "end1Id": "crm-001",
                "end2Id": "sc-002"
            },
            {
                "ucmdbId": "cont-001",
                "type": "containment",
                "end1Id": "fo-e-001",
                "end2Id": "sc-001"
            },
            {
                "ucmdbId": "usage-001",
                "type": "usage",
                "end1Id": "app-001",
                "end2Id": "sc-001"
            }
        ]
    }


@pytest.fixture
def sample_json_file(temp_dir, sample_json_data):
    """Creates a temporary JSON file with sample data."""
    json_file = temp_dir / "test_reporte.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(sample_json_data, f)
    return json_file


@pytest.fixture
def mock_ucmdb_config():
    """Provides a mock UCMDB config for testing."""
    from dataclasses import dataclass
    
    @dataclass
    class MockUCMDBConfig:
        USERNAME: str = "test_user"
        PASSWORD: str = "test_pass"
        AUTH_URL: str = "https://test.example.com/auth"
        BASE_URL: str = "https://test.example.com/api"
        DELETE_ENDPOINT: str = "https://test.example.com/delete"
        REQUEST_TIMEOUT: int = 30
        MAX_RETRIES: int = 3
        RETRY_DELAY: int = 2
        TARGET_NODE_TYPE: str = "clr_onyxservicecodes"
        NIT_FIELD_END1: str = "clr_onyxdb_company_nit"
        NIT_FIELD_END2: str = "clr_onyxdb_companynit"
        CONTENT_TYPE: str = "text/plain"
        CLIENT_CONTEXT: int = 1
        
        def validar(self):
            pass
    
    return MockUCMDBConfig()