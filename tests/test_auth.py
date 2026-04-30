"""
Tests for src/auth.py
"""

import pytest
from unittest.mock import Mock, patch
import requests


class TestAuthenticationError:
    """Tests for AuthenticationError exception."""
    
    def test_exception_exists(self):
        """Test AuthenticationError can be raised."""
        from src.auth import AuthenticationError
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Test error")


class TestConfigurationError:
    """Tests for ConfigurationError exception."""
    
    def test_exception_exists(self):
        """Test ConfigurationError can be raised."""
        from src.auth import ConfigurationError
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Test error")


class TestValidarCredenciales:
    """Tests for validar_credenciales function."""
    
    def test_returns_credentials_when_valid(self, mock_ucmdb_config):
        """Test returns username and password when valid."""
        from src.auth import validar_credenciales
        username, password = validar_credenciales(mock_ucmdb_config)
        assert username == "test_user"
        assert password == "test_pass"
    
    def test_raises_when_username_empty(self, mock_ucmdb_config):
        """Test raises when username is empty."""
        from src.auth import validar_credenciales, ConfigurationError
        mock_ucmdb_config.USERNAME = ""
        with pytest.raises(ConfigurationError):
            validar_credenciales(mock_ucmdb_config)
    
    def test_raises_when_password_empty(self, mock_ucmdb_config):
        """Test raises when password is empty."""
        from src.auth import validar_credenciales, ConfigurationError
        mock_ucmdb_config.PASSWORD = ""
        with pytest.raises(ConfigurationError):
            validar_credenciales(mock_ucmdb_config)


class TestConstruirPayloadAutenticacion:
    """Tests for construir_payload_autenticacion function."""
    
    def test_returns_correct_payload(self, mock_ucmdb_config):
        """Test returns correct authentication payload."""
        from src.auth import construir_payload_autenticacion
        payload = construir_payload_autenticacion("user", "pass", mock_ucmdb_config)
        assert payload["username"] == "user"
        assert payload["password"] == "pass"
        assert payload["clientContext"] == 1


class TestExtraerTokenDeRespuesta:
    """Tests for extraer_token_de_respuesta function."""
    
    def test_extracts_token_from_response(self):
        """Test extracts token from valid JSON response."""
        from src.auth import extraer_token_de_respuesta
        mock_response = Mock()
        mock_response.json.return_value = {"token": "test_token_123"}
        
        token = extraer_token_de_respuesta(mock_response)
        assert token == "test_token_123"
    
    def test_returns_none_when_no_token(self):
        """Test returns None when no token in response."""
        from src.auth import extraer_token_de_respuesta
        mock_response = Mock()
        mock_response.json.return_value = {"other": "data"}
        
        token = extraer_token_de_respuesta(mock_response)
        assert token is None
    
    def test_raises_when_invalid_json(self):
        """Test raises AuthenticationError on invalid JSON."""
        from src.auth import extraer_token_de_respuesta, AuthenticationError
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        with pytest.raises(AuthenticationError):
            extraer_token_de_respuesta(mock_response)


class TestObtenerTokenUCMDB:
    """Tests for obtener_token_ucmdb function."""
    
    @patch("src.auth.requests.post")
    def test_returns_token_on_success(self, mock_post, mock_ucmdb_config):
        """Test returns token when authentication succeeds."""
        from src.auth import obtener_token_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "jwt_token_abc"}
        mock_post.return_value = mock_response
        
        token = obtener_token_ucmdb(mock_ucmdb_config)
        assert token == "jwt_token_abc"
    
    @patch("src.auth.requests.post")
    def test_returns_none_on_auth_failure(self, mock_post, mock_ucmdb_config):
        """Test returns None when authentication fails."""
        from src.auth import obtener_token_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        token = obtener_token_ucmdb(mock_ucmdb_config)
        assert token is None
    
    @patch("src.auth.requests.post")
    def test_returns_none_on_server_error(self, mock_post, mock_ucmdb_config):
        """Test returns None on server error."""
        from src.auth import obtener_token_ucmdb
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        token = obtener_token_ucmdb(mock_ucmdb_config)
        assert token is None


class TestVerificarConfiguracion:
    """Tests for verificar_configuracion function."""
    
    def test_returns_true_when_config_valid(self, mock_ucmdb_config):
        """Test returns True when configuration is valid."""
        from src.auth import verificar_configuracion
        result = verificar_configuracion(mock_ucmdb_config)
        assert result == True
    
    def test_returns_false_when_config_invalid(self):
        """Test returns False when config is invalid."""
        from src.auth import verificar_configuracion, ConfigurationError
        from src.config import UCMDBConfig
        
        # Create config with empty credentials
        config = UCMDBConfig()
        config.USERNAME = ""
        config.PASSWORD = ""
        
        result = verificar_configuracion(config)
        assert result == False