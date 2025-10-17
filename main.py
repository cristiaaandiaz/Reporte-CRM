from auth import obtener_token_ucmdb
from report import (
    consultar_reporte_ucmdb,
    filtrar_cis_por_tipo_servicecodes,
    extraer_datos_relevantes_servicecodes,
    validar_nit_en_relaciones_invertidas
)
from datetime import datetime
import os
import json

def main():
    print("Iniciando autenticación con UCMDB...")
    token = obtener_token_ucmdb()

    if not token:
        print("No se pudo obtener el token. Finalizando ejecución.")
        return

    print("Consultando reporte de contratos CRM...")
    reporte = consultar_reporte_ucmdb(token)

    if not reporte:
        print("No se pudo obtener el reporte.")
        return


    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta_ejecucion = os.path.join("reports", f"ejecucion_{timestamp}")
    os.makedirs(carpeta_ejecucion, exist_ok=True)

    archivo_reporte = os.path.join(carpeta_ejecucion, f"reporte_{timestamp}.json")

    try:
        json_data = json.loads(reporte)
    except json.JSONDecodeError:
        print("El contenido del reporte no es un JSON válido.")
        return

    with open(archivo_reporte, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

    print(f"Reporte completo guardado en: {archivo_reporte}")

    print("Filtrando objetos de tipo 'clr_onyxservicecodes'...")
    cis_filtrados = filtrar_cis_por_tipo_servicecodes(json_data)
    cis_log = extraer_datos_relevantes_servicecodes(cis_filtrados)

    print(f"Total de objetos filtrados en memoria: {len(cis_log)}")

    inconsistencias = validar_nit_en_relaciones_invertidas(json_data)

    print(f"Relaciones con NIT diferentes encontradas: {len(inconsistencias)}")
    for rel_id in inconsistencias:
        print(f"Inconsistencia en relación con ucmdbId: {rel_id}")

    if inconsistencias:
        archivo_inconsistencias = os.path.join(carpeta_ejecucion, "inconsistencias.txt")
        with open(archivo_inconsistencias, "w", encoding="utf-8") as f:
            for i, rel_id in enumerate(inconsistencias, start=1):
                f.write(f"{i}. {rel_id}\n")
        print(f"Inconsistencias guardadas en: {archivo_inconsistencias}")
    else:
        print("No se encontraron inconsistencias. No se generó archivo.")
if __name__ == "__main__":
    main()