"""
Scraper de novedades DPPJ -> Supabase.
Version con diagnostico detallado: cada paso avisa explicitamente si
funciono o si fallo, y por que, para no tener que adivinar mirando logs.
"""

import os
import sys

import requests
from bs4 import BeautifulSoup


def paso(mensaje):
    print(f"\n=== {mensaje} ===", flush=True)


def obtener_noticias():
    URL_FUENTE = "https://www.gba.gob.ar/dppj/comunicaciones"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; NovedadesJuridicasBot/0.1)"}

    resp = requests.get(URL_FUENTE, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    tarjetas = soup.find_all("div", class_="node-noticias-personas-juridicas")

    noticias = []
    for tarjeta in tarjetas:
        titulo_tag = tarjeta.select_one(".field-name-title h2 a")
        if not titulo_tag:
            continue

        titulo = titulo_tag.get_text(strip=True)
        link_relativo = titulo_tag.get("href", "")
        link = (
            link_relativo
            if link_relativo.startswith("http")
            else f"https://www.gba.gob.ar{link_relativo}"
        )

        volanta_tag = tarjeta.select_one(".field-volanta-noticia .field-item")
        volanta = volanta_tag.get_text(strip=True) if volanta_tag else ""

        bajada_tag = tarjeta.select_one(".field-bajada-noticia-gba .field-item")
        bajada = bajada_tag.get_text(strip=True) if bajada_tag else ""

        noticias.append(
            {
                "fuente": "DPPJ",
                "titulo": titulo,
                "volanta": volanta,
                "bajada": bajada,
                "url": link,
            }
        )

    return noticias


def main():
    # --- PASO 1: variables de entorno (secrets de GitHub) ---
    paso("PASO 1: Chequeando variables de entorno")

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    if not supabase_url:
        print("FALTA la variable SUPABASE_URL.")
        print("Revisá: Settings -> Secrets and variables -> Actions -> ¿existe SUPABASE_URL?")
        sys.exit(1)

    if not supabase_key:
        print("FALTA la variable SUPABASE_KEY.")
        print("Revisá: Settings -> Secrets and variables -> Actions -> ¿existe SUPABASE_KEY?")
        sys.exit(1)

    print(f"SUPABASE_URL presente, empieza con: {supabase_url[:25]}...")
    print(f"SUPABASE_KEY presente, largo: {len(supabase_key)} caracteres")

    # --- PASO 2: conectar a Supabase ---
    paso("PASO 2: Conectando a Supabase")
    try:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        print("Cliente de Supabase creado sin error.")
    except Exception as e:
        print(f"FALLO al crear el cliente de Supabase: {type(e).__name__}: {e}")
        sys.exit(1)

    # --- PASO 3: probar que la tabla existe y se puede leer ---
    paso("PASO 3: Probando lectura de la tabla novedades_juridicas")
    try:
        prueba = supabase.table("novedades_juridicas").select("url").limit(1).execute()
        print(f"Lectura OK. Filas existentes (muestra): {len(prueba.data)}")
    except Exception as e:
        print(f"FALLO al leer la tabla: {type(e).__name__}: {e}")
        print("Posibles causas: la tabla no existe, el nombre está mal escrito,")
        print("o la key no tiene permiso de lectura.")
        sys.exit(1)

    # --- PASO 4: scrapear el sitio de DPPJ ---
    paso("PASO 4: Descargando y parseando la página de DPPJ")
    try:
        noticias = obtener_noticias()
        print(f"Encontradas en el sitio: {len(noticias)}")
        if noticias:
            print(f"Ejemplo del primer item: {noticias[0]['titulo']}")
    except Exception as e:
        print(f"FALLO al descargar/parsear la página: {type(e).__name__}: {e}")
        sys.exit(1)

    if not noticias:
        print("El scraper no encontró ninguna noticia. Puede que el sitio haya")
        print("cambiado su estructura HTML. Revisar selectores en obtener_noticias().")
        sys.exit(1)

    # --- PASO 5: comparar contra lo ya guardado ---
    paso("PASO 5: Comparando contra lo ya guardado en Supabase")
    try:
        existentes = supabase.table("novedades_juridicas").select("url").execute()
        urls_guardadas = {fila["url"] for fila in existentes.data}
        print(f"Ya había {len(urls_guardadas)} url(s) guardada(s).")
    except Exception as e:
        print(f"FALLO al traer las urls existentes: {type(e).__name__}: {e}")
        sys.exit(1)

    nuevas = [n for n in noticias if n["url"] not in urls_guardadas]
    print(f"Novedades nuevas detectadas: {len(nuevas)}")

    if not nuevas:
        paso("RESULTADO: sin novedades nuevas, no hay nada para insertar")
        return

    # --- PASO 6: insertar lo nuevo ---
    paso("PASO 6: Insertando novedades nuevas en Supabase")
    try:
        resultado = supabase.table("novedades_juridicas").insert(nuevas).execute()
        print(f"Insertadas {len(resultado.data)} fila(s) correctamente.")
        for n in nuevas:
            print(f"  - [{n['fuente']}] {n['titulo']}")
    except Exception as e:
        print(f"FALLO al insertar: {type(e).__name__}: {e}")
        print("Posibles causas: permisos de escritura (RLS), columnas que no")
        print("coinciden con la tabla, o valores duplicados en 'url' (debe ser UNIQUE).")
        sys.exit(1)

    paso("RESULTADO: proceso terminado sin errores")


if __name__ == "__main__":
    main()

