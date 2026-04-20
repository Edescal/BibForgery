#!/usr/bin/python3 -u
"""
BibForgery v1.0
Script para obtener artículos de Scopus y convertirlos a distintos formatos.

Creado por:
Eduardo Escalante Pacheco
17-abril-2026

#### Uso:
    python3 bibforgery.py [--fetch AUTHOR_ID] [--to-bibtex] [-f {text,json}] [-i INPUT] [-o OUTPUT]
    python3 bibforgery.py [-f {text,json,pdf}] [-i INPUT] [-o OUTPUT]

#### Opciones:
    --fetch AUTHOR_ID   (opcional) Obtiene artículos del autor desde Scopus
    --to-bibtex         (opcional) Transforma la respuesta a formato BibTex
    --parse             (opcional) Indica que se va a parsear un archivo BibTex
    -f, --format        (opcional) Formato de salida: text o json
    -i, --input         (opcional) Archivo de entrada (default: input.txt)
    -o, --output        (opcional) Archivo de salida (default: output.txt)

#### Ejemplos:
    python3 bibforgery.py --fetch 56000743500
    python3 bibforgery.py -f json -i data.txt -o out.json
    python3 bibforgery.py -f pdf -i input.bib -o output.pdf
"""

from bibtexparser.model import Entry, Field
from collections.abc import MutableSequence
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import bibtexparser, argparse, json, requests, time, os
from jinja2 import Template
from weasyprint import HTML, CSS
from collections import defaultdict


env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
ELSEVIER_INSTTOKEN = os.getenv("ELSEVIER_INSTTOKEN")


def get_grouped_entries(bib_entries: MutableSequence[Entry]):
    """
    Args:
        bib_entries (MutableSequence[Entry]): secuencia de entradas generada por bibtexparser

    Clasifica por año una secuencia de entradas
    generadas por bibtexparser. Si una entrada no
    tiene año la clasifica como "Sin Año".
    """
    
    grouped = defaultdict(list)
    for entry in bib_entries:
        year_field = entry.get("year")
        year = year_field.value if year_field else "Sin Año"

        citation_html = process_single_entry_as_html(entry)
        grouped[year].append(citation_html)

    sorted_years = sorted(grouped.keys(), reverse=True)
    return [(y, grouped[y]) for y in sorted_years]


def transform_authors(author_field: Field):
    """
    Convertir datos de autores en formato
    Bibtex a un string "Apellido, N; Apellido, N"

    Args:
        author_field (Field): entrada de autores generada por bibtexparser
    """
    authors = author_field.value.split(" and ")
    author_list = []
    for a in authors:
        parts = a.split(",")
        family = parts[0]
        names = parts[1].strip().split(" ")
        initials = ""
        for n in names:
            initials += f"{n[0]}."
        author_list.append(f"{family}, {initials}")
    result = "; ".join(author_list)
    return result


def process_single_entry_as_html(entry: Entry):
    """
    Args:
        entry (Entry): Entrada generada por bibtexparser

    Returns:
        String de HTML de una cita bibliográfica
        a partir de una entrada en formato bibtex
    """
    author_string = entry.get("author")
    author_string = transform_authors(author_string)

    title, journal, year = (
        entry.get("title"),
        entry.get("journal"),
        entry.get("year"),
    )

    v, n, p, d = (
        entry.get("volume"),
        entry.get("number"),
        entry.get("pages"),
        entry.get("doi"),
    )

    res = f'{author_string} <span style="font-style: italic;">{title.value}</span>. {journal.value}'
    if year:
        res += f' <span style="font-weight: bold;">{year.value}</span>'
    if v or n or p:
        res += ","
        if v:
            res += f" {v.value}"
        if n:
            res += f"({n.value})"
        if p:
            res += f", {p.value}"
    if d:
        res += f'. DOI: <a href="https://doi.org/{d.value}" target="_blank" rel="noopener noreferrer" style="color: #0563C1; text-decoration: underline;">https://doi.org/{d.value}</a>'

    return res


def process_entries_as_text(bib_entries: MutableSequence[Entry]):
    """
    Args:
        bib_entries (MutableSequence[Entry]): secuencia de entradas generada por bibtexparser

    Returns:
        Generador que devuelve una a una (yield) citas
        en texto plano a partir de una secuencia de
        entradas en formato bibtex
    """
    entries = 0
    for entry in bib_entries:
        entries += 1
        author_string = entry.get("author")
        author_string = transform_authors(author_string)

        title, journal, year = (
            entry.get("title"),
            entry.get("journal"),
            entry.get("year"),
        )

        v, n, p, d = (
            entry.get("volume"),
            entry.get("number"),
            entry.get("pages"),
            entry.get("doi"),
        )

        res = f"{author_string} {title.value}. {journal.value} {year.value}"
        if v:
            res += f", {v.value}"
        if n:
            res += f"({n.value})"
        if p:
            res += f", {p.value}"
        if d:
            res += f". DOI: {d.value}"

        yield res + "\n" * 2
    print(f"Total entradas: {entries}")


def process_entries_as_json(bib_entries: MutableSequence[Entry]):
    """
    Args:
        bib_entries (MutableSequence[Entry]): secuencia de entradas generada por bibtexparser

    Returns:
        Generador que devuelve una a una (yield) citas
        en formato objeto JSON a partir de una secuencia
        de entradas en formato bibtex
    """

    for entry in bib_entries:
        data = {
            "id": entry.key,
            "authors": transform_authors(entry.get("author")),
            "title": entry.get("title").value if entry.get("title") else "",
            "year": int(entry.get("year").value) if entry.get("year") else None,
            "journal": entry.get("journal").value if entry.get("journal") else "",
            "doi": entry.get("doi").value if entry.get("doi") else None,
            "volume": entry.get("volume").value if entry.get("volume") else "",
            "number": entry.get("number").value if entry.get("number") else "",
            "pages": entry.get("pages").value if entry.get("pages") else "",
        }
        yield data


def is_valid_json(filename):
    """
    Función para validar que un archivo de JSON
    es válido y puede abrirse sin producir errores

    Args:
        filename (string): archivo de entrada
    """

    try:
        with open(filename, "r", encoding="utf-8") as f:
            json.load(f)
        print("[•] Valid JSON")
    except json.JSONDecodeError as e:
        print(f"[X] Invalid JSON: {e}")


def generate_txt(input, output):
    """
    Genera citas en texto plano a partir
    de un archivo en formato Bibtex y lo
    guarda en un archivo

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """

    with open(input, "r", encoding="utf-8") as file:
        bibtext = bibtexparser.parse_string(file.read())

    if bibtext.failed_blocks:
        print(f"[Warning] — Found {len(bibtext.failed_blocks)} Failed Blocks")
        for block in bibtext.failed_blocks:
            print(f"\tLine: {block.start_line}")
            print(f"\tError: {block.error}")

    with open(output, "w", encoding="utf-8") as file:
        file.writelines(process_entries_as_text(bibtext.entries))

    print("[Info] — Data created")


def generate_json(input, output):
    """
    Genera citas en formato JSON a partir
    de un archivo en formato Bibtex y lo
    guarda en un archivo

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """

    with open(input, "r", encoding="utf-8") as file:
        bibtext = bibtexparser.parse_string(file.read())

    if bibtext.failed_blocks:
        print(f"[Warning] — Found {len(bibtext.failed_blocks)} Failed Blocks")
        for block in bibtext.failed_blocks:
            print(f"\tLine: {block.start_line}")
            print(f"\tError: {block.error}")

    with open(output, "w", encoding="utf-8") as f:
        f.write("[")

        yielder = process_entries_as_json(bibtext.entries)
        try:
            first = next(yielder)
            f.write(json.dumps(first, separators=(",", ":"), ensure_ascii=False))
            for item in yielder:
                f.write(",")
                f.write(json.dumps(item, separators=(",", ":"), ensure_ascii=False))
        except StopIteration:
            pass

        f.write("]")

    print("[Info] — JSON created")
    is_valid_json(output)


def generate_pdf(input, output):
    """
    Generador de archivo PDF a partir
    de un archivo en formato Bibtex.

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """

    with open(input, "r", encoding="utf-8") as file:
        bibtext = bibtexparser.parse_string(file.read())

    if bibtext.failed_blocks:
        print(f"[Warning] — Found {len(bibtext.failed_blocks)} Failed Blocks")
        for block in bibtext.failed_blocks:
            print(f"\tLine: {block.start_line}")
            print(f"\tError: {block.error}")
            
    base_path = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_path, "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as html:
        plantilla_html = html.read()

    context = {
        "grouped_data": get_grouped_entries(bibtext.entries),
        "date": datetime.now().strftime("%B %d, %Y"),
    }
    render = Template(plantilla_html).render(data=context)
    styles = CSS(filename="templates/styles.css")
    HTML(string=render, base_url="templates/").write_pdf(
        output,
        stylesheets=[styles],
    )
    print("[Info] — PDF created")


def get_all_papers(author_id, output="output.json", max_entries=500):
    headers = {"X-ELS-APIKey": ELSEVIER_API_KEY, "X-ELS-Insttoken": ELSEVIER_INSTTOKEN, "Accept": "application/json"}

    start = 0
    count = 25
    all_entries = []

    iter = 1
    while True:
        print(f"Query: {iter}")
        iter += 1

        params = {
            "query": f"AU-ID({author_id})",
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
        start += count

        print(f"Descargados: {len(all_entries)}/{total}")
        
        if start >= total or start >= max_entries:
            break

        time.sleep(1)

    with open(output, "w", encoding="utf-8") as f:
        json.dump({"search-results": {"entry": all_entries}}, f, indent=2, ensure_ascii=False)

    print(f"\nListo: {output}")


def json_to_bibtex(input_file="referencias.json", output_file="referencias.bib"):
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

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

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_bib)

    print(f"Listo: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--fetch", metavar="AUTHOR ID", default="", help="Fetch Scopus API with AUTHOR_ID")
    parser.add_argument("--to-bibtex", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument(
        "--max-entries",
        metavar="",
        type=int,
        default=500,
        help="Límite máximo de artículos recuperados (útil para testing)",
    )

    parser.add_argument("-i", "--input", metavar="BibTex", default="input.txt", help="Nombre de archivo de entrada")
    parser.add_argument("-o", "--output", metavar="JSON, TXT", default="", help="Nombre de aArchivo de salida")
    parser.add_argument("--parse", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument(
        "-f",
        "--format",
        metavar="{text,json,pdf}",
        choices=["text", "json", "pdf"],
        default="",
        help="Formato de salida",
    )

    args = parser.parse_args()

    # Si se usan los args --fetch <AUTHOR_ID>
    if args.fetch:
        get_all_papers(args.fetch, args.output if args.output else "fetch-result.json", args.max_entries)
        # --to-bibtex
        if args.to_bibtex:
            input_file = Path(args.output if args.output else "fetch-result.json")
            output_file = input_file.with_name(input_file.stem + "-parsed.bib")
            json_to_bibtex(input_file, output_file)
        return

    if args.to_bibtex:
        input_file = Path(args.input)
        output_file = input_file.with_name(input_file.stem + "-parsed.bib")
        print(input_file)
        print(output_file)
        json_to_bibtex(args.input, output_file)
        return

    if not args.parse or not args.format:
        parser.error("Debes especificar el tipo de uso: --fetch ó --parse")

    if args.format == "json":
        generate_json(args.input, args.output if args.output else "output.json")
    elif args.format == "text":
        generate_txt(args.input, args.output if args.output else "output.txt")
    elif args.format == "pdf":
        generate_pdf(args.input, args.output if args.output else "output.pdf")


if __name__ == "__main__":
    main()
