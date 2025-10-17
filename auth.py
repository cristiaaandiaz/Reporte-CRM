import requests
import urllib3
import os
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

def obtener_token_ucmdb():
    """
    Autentica contra la API de UCMDB y obtiene un token JWT.

    Returns:
        str: Token JWT si la autenticación es exitosa.
        None: Si ocurre un error.
    """
    auth_url = "https://ucmdbapp.triara.co:8443/rest-api/authenticate"

    username = os.getenv("UCMDB_USER")
    password = os.getenv("UCMDB_PASS")

    if not username or not password:
        print("Usuario o contraseña no definidos en el archivo .env")
        return None

    payload = {
        "username": username,
        "password": password,
        "clientContext": 1
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(auth_url, json=payload, headers=headers, verify=False)

        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        else:
            print(f"Error al autenticar. Código: {response.status_code}")
            print("Detalle:", response.text)
            return None

    except requests.exceptions.RequestException as e:
        print("Error de conexión o solicitud:", str(e))
        return None