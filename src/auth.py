"""
Módulo de Autenticación para UCMDB.

Gestiona la autenticación con la API REST de UCMDB y obtiene
tokens JWT para peticiones subsecuentes.
"""

from typing import Optional, Tuple

import requests
import urllib3

from .config import UCMDBConfig
from .logger_config import obtener_logger

# Desactivar advertencias SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = obtener_logger(__name__)


class AuthenticationError(Exception):
    """Excepción personalizada para errores de autenticación UCMDB."""
    pass


class ConfigurationError(Exception):
    """Excepción personalizada para errores de configuración."""
    pass


def validar_credenciales(config: UCMDBConfig) -> Tuple[str, str]:
    """
    Valida que las credenciales estén configuradas.

    Args:
        config: Configuración de UCMDB

    Returns:
        Tuple[str, str]: Usuario y contraseña

    Raises:
        ConfigurationError: Si las credenciales no están definidas.
    """
    username = config.USERNAME
    password = config.PASSWORD

    credenciales_faltantes = []
    
    if not username:
        credenciales_faltantes.append("UCMDB_USER")
    if not password:
        credenciales_faltantes.append("UCMDB_PASS")
    
    if credenciales_faltantes:
        mensaje = (
            f"Credenciales no definidas en el archivo .env: "
            f"{', '.join(credenciales_faltantes)}"
        )
        logger.error(mensaje)
        raise ConfigurationError(mensaje)
    
    logger.debug("Credenciales validadas correctamente")
    return username, password


def construir_payload_autenticacion(
    username: str, 
    password: str,
    config: UCMDBConfig
) -> dict:
    """
    Construye el payload para la petición de autenticación.

    Args:
        username: Nombre de usuario de UCMDB
        password: Contraseña de UCMDB
        config: Configuración de UCMDB

    Returns:
        Diccionario con los datos de autenticación
    """
    return {
        "username": username,
        "password": password,
        "clientContext": config.CLIENT_CONTEXT
    }


def extraer_token_de_respuesta(response: requests.Response) -> Optional[str]:
    """
    Extrae el token JWT de la respuesta de autenticación.

    Args:
        response: Respuesta HTTP de la petición de autenticación

    Returns:
        Token JWT si existe, None si no se encuentra

    Raises:
        AuthenticationError: Si la respuesta no contiene JSON válido
    """
    try:
        data = response.json()
        token = data.get("token")
        
        if not token:
            logger.warning("La respuesta no contiene un token")
            return None
        
        logger.debug("Token extraído exitosamente")
        return token
        
    except ValueError as e:
        mensaje = f"Respuesta no contiene JSON válido: {e}"
        logger.error(mensaje)
        raise AuthenticationError(mensaje)


def autenticar_con_api(
    username: str, 
    password: str,
    config: UCMDBConfig
) -> requests.Response:
    """
    Realiza la petición de autenticación a la API de UCMDB.

    Args:
        username: Nombre de usuario de UCMDB
        password: Contraseña de UCMDB
        config: Configuración de UCMDB

    Returns:
        requests.Response: Respuesta HTTP de la API

    Raises:
        AuthenticationError: Si hay problemas de conexión o timeout
    """
    payload = construir_payload_autenticacion(username, password, config)
    headers = {"Content-Type": "application/json"}

    try:
        logger.info(f"Autenticando con UCMDB en: {config.AUTH_URL}")
        response = requests.post(
            config.AUTH_URL,
            json=payload,
            headers=headers,
            verify=False,
            timeout=config.REQUEST_TIMEOUT
        )
        
        logger.debug(f"Respuesta recibida con código: {response.status_code}")
        return response
        
    except requests.exceptions.Timeout:
        mensaje = (
            f"Timeout al conectar con UCMDB después de {config.REQUEST_TIMEOUT} segundos"
        )
        logger.error(mensaje)
        raise AuthenticationError(mensaje)
        
    except requests.exceptions.ConnectionError as e:
        mensaje = f"Error de conexión con UCMDB: {str(e)}"
        logger.error(mensaje)
        raise AuthenticationError(mensaje)
        
    except requests.exceptions.RequestException as e:
        mensaje = f"Error en la petición de autenticación: {str(e)}"
        logger.error(mensaje)
        raise AuthenticationError(mensaje)


def obtener_token_ucmdb(config: Optional[UCMDBConfig] = None) -> Optional[str]:
    """
    Autentica contra la API de UCMDB y obtiene un token JWT.

    Este es el punto de entrada principal para la autenticación.
    Valida las credenciales, realiza la autenticación
    y extrae el token JWT de la respuesta.

    Args:
        config: Configuración de UCMDB (usa instancia global si no se proporciona)

    Returns:
        Token JWT si la autenticación es exitosa, None si falla

    Example:
        >>> token = obtener_token_ucmdb()
        >>> if token:
        ...     print("Autenticación exitosa")
        ... else:
        ...     print("Falló la autenticación")
    
    Note:
        Esta función requiere que las variables UCMDB_USER y UCMDB_PASS
        estén definidas en el archivo .env del proyecto.
    """
    if config is None:
        from .config import ucmdb_config
        config = ucmdb_config
    
    try:
        # Paso 1: Validar credenciales
        username, password = validar_credenciales(config)
        
        # Paso 2: Autenticar con la API
        response = autenticar_con_api(username, password, config)
        
        # Paso 3: Verificar código de respuesta
        if response.status_code == 200:
            logger.info("Autenticación exitosa con UCMDB")
            token = extraer_token_de_respuesta(response)
            
            if token:
                logger.info("Token JWT obtenido correctamente")
                return token
            else:
                logger.error("Token no encontrado en la respuesta")
                return None
        else:
            logger.error(
                f"Error al autenticar. Código HTTP: {response.status_code}"
            )
            logger.debug(f"Detalle de respuesta: {response.text}")
            return None
    
    except ConfigurationError as e:
        logger.error(f"Error de configuración: {e}")
        return None
    
    except AuthenticationError as e:
        logger.error(f"Error de autenticación: {e}")
        return None
    
    except Exception as e:
        logger.exception(f"Error inesperado durante la autenticación: {e}")
        return None


def verificar_configuracion(config: Optional[UCMDBConfig] = None) -> bool:
    """
    Verifica que la configuración de autenticación sea válida.

    Útil para health checks o validaciones previas sin realizar
    una autenticación completa.

    Args:
        config: Configuración de UCMDB (usa instancia global si no se proporciona)

    Returns:
        True si la configuración es válida, False en caso contrario
    """
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
