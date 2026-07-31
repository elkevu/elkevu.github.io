"""
Scraper de novedades DPPJ -> Supabase.
Este script NO lo corrés vos: lo corre GitHub Actions solo, todos los días.
Lee las credenciales de Supabase desde variables de entorno (los "Secrets"
que vas a configurar en GitHub, paso 3 del README).
"""

import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client

URL_FUENTE = "https://www.gba.gob.ar/dppj/comunicaciones"

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def obtener_noticias():
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
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    noticias = obtener_noticias()
    print(f"Encontradas en el sitio: {len(noticias)}")

    # Traemos las urls que ya tenemos guardadas, para no duplicar.
    existentes = supabase.table("novedades_juridicas").select("url").execute()
    urls_guardadas = {fila["url"] for fila in existentes.data}

    nuevas = [n for n in noticias if n["url"] not in urls_guardadas]

    if not nuevas:
        print("No hay novedades nuevas desde la última corrida.")
        return

    supabase.table("novedades_juridicas").insert(nuevas).execute()
    print(f"Insertadas {len(nuevas)} novedad(es) nueva(s):")
    for n in nuevas:
        print(f"  - [{n['fuente']}] {n['titulo']}")


if __name__ == "__main__":
    main()
