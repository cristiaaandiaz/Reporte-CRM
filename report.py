import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def consultar_reporte_ucmdb(token):
    reporte_url = "https://10.110.0.62:8443/rest-api/topology"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain"
    }
    body = "Reporte_Clientes_Onyx-uCMDB"

    try:
        response = requests.post(reporte_url, data=body, headers=headers, verify=False)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error al consultar el reporte. Código: {response.status_code}")
            print("Detalle:", response.text)
            return None
    except requests.exceptions.RequestException as e:
        print("Error de conexión o solicitud:", str(e))
        return None
def filtrar_cis_por_tipo_servicecodes(json_data):
    cis = json_data.get("cis", [])
    if not isinstance(cis, list):
        print("Advertencia: El contenido recibido no es una lista.")
        return []
    return [obj for obj in cis if obj.get("type") == "clr_onyxservicecodes"]

def extraer_datos_relevantes_servicecodes(cis_filtrados):
    resultado = []
    for obj in cis_filtrados:
        properties = obj.get("properties", {})
        resultado.append({
            "type": obj.get("type"),
            "display_label": properties.get("display_label"),
            "company_nit": properties.get("clr_onyxdb_company_nit")
        })
    return resultado

def validar_nit_en_relaciones_invertidas(json_data):
    cis = json_data.get("cis", [])
    relaciones = json_data.get("relations", [])

    # Indexar todos los nodos CIS por su ucmdbId
    nodos_por_id = {obj.get("ucmdbId"): obj for obj in cis}

    inconsistencias = []

    print(f"Procesando {len(relaciones)} relaciones...")

    for rel in relaciones:
        rel_id = rel.get("ucmdbId")
        end1_id = rel.get("end1Id")
        end2_id = rel.get("end2Id")

        nodo_end1 = nodos_por_id.get(end1_id)
        nodo_end2 = nodos_por_id.get(end2_id)

        # Validar que ambos nodos existan
        if not nodo_end1 or not nodo_end2:
            continue

        # Obtener los NITs
        nit_end1 = nodo_end1.get("properties", {}).get("clr_onyxdb_company_nit")
        nit_end2 = nodo_end2.get("properties", {}).get("clr_onyxdb_companynit")

        # Validar que ambos NIT existan
        if nit_end1 is None or nit_end2 is None:
            continue

        # Comparar y guardar si son diferentes
        if nit_end1.strip() != nit_end2.strip():
            inconsistencias.append(rel_id)

    print(f"Total de inconsistencias encontradas: {len(inconsistencias)}")
    return inconsistencias

