"""
Autenticación JWT con UCMDB.
"""

from typing import Optional, Tuple

import requests
import urllib3

from .config import UCMDBConfig, VERIFY_SSL
from .logger_config import obtener_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


class AuthenticationError(Exception):
    """Excepción para errores de autenticación UCMDB."""
    pass


class ConfigurationError(Exception):
    """Excepción para errores de configuración."""
    pass


def validar_credenciales(config: UCMDBConfig) -> Tuple[str, str]:
    """Valida que las credenciales estén configuradas."""
    username = config.USERNAME
    password = config.PASSWORD
    
    credenciales_faltantes = []
    if not username:
        credenciales_faltantes.append("UCMDB_USER")
    if not password:
        credenciales_faltantes.append("UCMDB_PASS")
    
    if credenciales_faltantes:
        raise ConfigurationError(f"Credenciales faltantes: {', '.join(credenciales_faltantes)}")
    
    return username, password


def construir_payload_autenticacion(username: str, password: str, config: UCMDBConfig) -> dict:
    """Construye el payload para autenticación."""
    return {
        "username": username,
        "password": password,
        "clientContext": config.CLIENT_CONTEXT
    }


def extraer_token_de_respuesta(response: requests.Response) -> Optional[str]:
    """Extrae el token JWT de la respuesta."""
    try:
        data = response.json()
        token = data.get("token")
        return token if token else None
    except ValueError as e:
        raise AuthenticationError(f"Respuesta no contiene JSON válido: {e}")


def autenticar_con_api(username: str, password: str, config: UCMDBConfig) -> requests.Response:
    """Realiza la petición de autenticación a la API de UCMDB."""
    payload = construir_payload_autenticacion(username, password, config)
    headers = {"Content-Type": "application/json"}
    
    try:
        logger.info(f"Autenticando con UCMDB: {config.AUTH_URL}")
        response = requests.post(
            config.AUTH_URL,
            json=payload,
            headers=headers,
            verify=VERIFY_SSL,
            timeout=config.REQUEST_TIMEOUT
        )
        logger.debug(f"Respuesta HTTP: {response.status_code}")
        return response
        
    except requests.exceptions.Timeout as e:
        raise AuthenticationError(f"Timeout después de {config.REQUEST_TIMEOUT}s: {e}")
    except requests.exceptions.ConnectionError as e:
        raise AuthenticationError(f"Error de conexión: {e}")
    except requests.exceptions.RequestException as e:
        raise AuthenticationError(f"Error en petición: {e}")


def obtener_token_ucmdb(config: Optional[UCMDBConfig] = None) -> Optional[str]:
    """
    Autentica contra UCMDB y obtiene un token JWT.
    
    Returns:
        Token JWT si es exitoso, None si falla.
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    try:
        username, password = validar_credenciales(config)
        response = autenticar_con_api(username, password, config)
        
        if response.status_code == 200:
            token = extraer_token_de_respuesta(response)
            if token:
                logger.info("Token JWT obtenido correctamente")
                return token
            logger.error("Token no encontrado en respuesta")
            return None
        
        logger.error(f"Error autenticación. HTTP: {response.status_code}")
        return None
    
    except ConfigurationError as e:
        logger.error(f"Error de configuración: {e}")
        return None
    except AuthenticationError as e:
        logger.error(f"Error de autenticación: {e}")
        return None


def verificar_configuracion(config: Optional[UCMDBConfig] = None) -> bool:
    """Verifica que la configuración de autenticación sea válida."""
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    try:
        validar_credenciales(config)
        logger.info("Configuración de autenticación válida")
        return True
    except ConfigurationError:
        logger.warning("Configuración de autenticación inválida")
        return False