#!/usr/bin/python3 -u
"""
BibForgery v1.0
Script para obtener artículos de Scopus y convertirlos a distintos formatos.

Creado por:
Eduardo Escalante Pacheco
17-abril-2026

#### Uso:
    python3 bibforgery.py [--fetch AUTHOR_ID] [-f {text,json}] [-i INPUT] [-o OUTPUT]
    python3 bibforgery.py [-f {text,json,pdf}] [-i INPUT] [-o OUTPUT]

#### Opciones:
    --fetch AUTHOR_ID   (opcional) Obtiene artículos del autor desde Scopus
    --parse             (opcional) Indica que se va a parsear un archivo BibTex
    -f, --format        (opcional) Formato de salida: text o json
    -i, --input         (opcional) Archivo de entrada (default: input.txt)
    -o, --output        (opcional) Archivo de salida (default: output.txt)

#### Ejemplos:
    python3 bibforgery.py --fetch 56000743500
    python3 bibforgery.py -f txt -i data.bib -o out.txt
    python3 bibforgery.py -f json -i data.bib -o out.json
    python3 bibforgery.py -f pdf -i input.bib -o output.pdf
"""

from pathlib import Path
import requests, time


def get_data_from_file(input) -> str:
    input_path = Path(input).resolve()
    if not input_path.exists():
        print(f"Error: No se encuentra el archivo de entrada {input_path}")
        return
    with open(input_path, "r", encoding="utf-8") as file:
        data = file.read()
    return data


def fetch_papers(author_id, api_key="", inst_token="", max_entries=500):
    headers = {"X-ELS-APIKey": api_key, "X-ELS-Insttoken": inst_token, "Accept": "application/json"}

    start = 0
    count = 25
    all_entries = []

    iter = 1
    while True:
        print(f"Query {iter}", end="")
        iter += 1

        params = {
            "query": f"AU-ID({author_id}) AND (DOCTYPE(ar) OR DOCTYPE(re) OR DOCTYPE(ed))",
            "start": start,
            "count": count,
            "view": "COMPLETE",
            "sort": "-coverDate",
        }

        res = requests.get("https://api.elsevier.com/content/search/scopus", headers=headers, params=params)
        if res.status_code != 200:
            print("Error:", res.status_code, res.text)
            break
        data = res.json()
        entries = data.get("search-results", {}).get("entry", [])
        if not entries:
            break

        all_entries.extend(entries)
        total = int(data["search-results"]["opensearch:totalResults"])
        print(f" — Downloaded: {len(all_entries)}/{total}")
        time.sleep(0.4)

        next_limit = start + count
        if (next_limit) > max_entries:
            count = max_entries - start
        start += count

        if start >= total or start >= max_entries:
            break

    return {
        "search-results": {
            "entry": all_entries,
        },
    }


def data_to_bibtex(data) -> str:
    entries = data.get("search-results", {}).get("entry", [])

    full_bib = ""

    for entry in entries:
        authors = entry.get("author", [])
        author_list = [f"{a.get('surname','')}, {a.get('given-name','')}".strip(", ") for a in authors]
        authors_str = " and ".join(author_list) if author_list else entry.get("dc:creator", "Unknown")

        # Datos básicos
        title = entry.get("dc:title", "Untitled")
        journal = entry.get("prism:publicationName", "")
        date = entry.get("prism:coverDate", "0000-00-00")
        year = date[:4]
        month = date[5:7] if len(date) >= 7 else ""
        day = date[8:10] if len(date) >= 10 else ""
        doi = entry.get("prism:doi", "")
        volume = entry.get("prism:volume", "")
        issue = entry.get("prism:issueIdentifier", "")
        pages = entry.get("prism:pageRange", "")
        eid = entry.get("eid", "")

        # Key
        if doi:
            cite_key = doi.replace("/", "_").replace(".", "_")
        elif eid:
            cite_key = eid.replace("-", "_")
        else:
            main_auth = entry.get("dc:creator", "paper").split(",")[0]
            cite_key = f"{main_auth}_{year}"

        # BibTeX
        bib = f"@ARTICLE{{{cite_key},\n"
        bib += f"  author = {{{authors_str}}},\n"
        bib += f"  title = {{{title}}},\n"
        bib += f"  journal = {{{journal}}},\n"
        bib += f"  year = {{{year}}},\n"
        if month:
            bib += f"  month = {{{month}}},\n"
        if day:
            bib += f"  day = {{{day}}},\n"
        if volume:
            bib += f"  volume = {{{volume}}},\n"
        if issue:
            bib += f"  number = {{{issue}}},\n"
        if pages:
            bib += f"  pages = {{{pages}}},\n"
        if doi:
            bib += f"  doi = {{{doi}}},\n"
        if eid:
            bib += f"  url = {{https://www.scopus.com/inward/record.uri?eid={eid}}},\n"
        bib += f"  type = {{{entry.get('subtypeDescription', 'Article')}}}\n"
        bib += "}\n\n"

        full_bib += bib
    return full_bib

