from .parser import parse_bibtex, process_entries_as_json, process_entries_as_text, get_grouped_entries
from .libjabbrev2 import jabbreviation2
from jinja2 import Template
from datetime import datetime
import os, io, json


def dict_to_bibtex(data: dict) -> str:
    entries = data.get("papers", [])
    full_bib = ""

    for entry in entries:
        title = entry.get("dc:title", "")
        xml_title = entry.get("xml:title", "")
        authors = entry.get("author", [])
        author_list = [f"{a.get('surname','')}, {a.get('given-name','')}".strip(", ") for a in authors]
        authors_str = " and ".join(author_list) if author_list else "A. Unknown"

        journal = entry.get("prism:publicationName", "")
        date = entry.get("prism:coverDate", "0000-00-00")
        year = date[:4]
        month = date[5:7] if len(date) >= 7 else ""
        day = date[8:10] if len(date) >= 10 else ""
        volume = entry.get("prism:volume", "")
        issue = entry.get("prism:issueIdentifier", "")
        pages = entry.get("prism:pageRange", "")
        eid = entry.get("eid", "")
        citedby_count = int(entry.get("citedby-count", "0"))
        doi = entry.get("prism:doi", "")

        # Key
        if eid:
            cite_key = eid
        elif doi:
            cite_key = doi.replace("/", "_").replace(".", "_")
        else:
            main_auth = entry.get("dc:creator", "paper").split(",")[0]
            cite_key = f"{main_auth}_{year}"

        # BibTeX
        bib = f"@ARTICLE{{{cite_key},\n"
        bib += f"  author = {{{authors_str}}},\n"
        bib += f"  title = {{{title}}},\n"
        bib += f"  xml_title = {{{xml_title}}},\n"
        bib += f"  journal = {{{journal}}},\n"
        bib += f"  journal_abbrev = {{{jabbreviation2(journal)}}},\n"
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
        if citedby_count:
            bib += f"  citedby_count = {{{citedby_count}}},\n"
        if eid:
            bib += f"  url = {{https://www.scopus.com/inward/record.uri?eid={eid}}},\n"
        bib += f"  type = {{{entry.get('subtypeDescription', 'Article')}}}\n"
        bib += "}\n\n"

        full_bib += bib
    return full_bib


def generate_txt(input: str) -> bytes:
    """
    Genera citas en texto plano a partir
    de un archivo en formato Bibtex y lo
    guarda en un archivo

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """

    bibtext = parse_bibtex(input)

    buffer = io.BytesIO()
    for chunk in process_entries_as_text(bibtext.entries):
        buffer.write(chunk.encode("utf-8"))
    buffer.seek(0)
    return buffer


def generate_json(input, full=False) -> bytes:
    bibtext = parse_bibtex(input)

    buffer = io.BytesIO()
    buffer.write(b"[")
    yielder = process_entries_as_json(bibtext.entries, full)
    try:
        first = next(yielder)
        buffer.write(json.dumps(first, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        for item in yielder:
            buffer.write(b",")
            buffer.write(json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    except StopIteration:
        pass
    buffer.write(b"]")
    buffer.seek(0)
    return buffer


def generate_pdf(input) -> bytes | None:
    """
    Generador de archivo PDF a partir
    de un archivo en formato Bibtex.

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """

    from weasyprint import HTML, CSS

    bibtext = parse_bibtex(input)

    base_path = os.path.dirname(os.path.abspath(__file__))
    templates_path = os.path.join(base_path, "templates/")
    html_path = os.path.join(base_path, "templates", "index.html")
    css_path = os.path.join(base_path, "templates", "styles.css")

    with open(html_path, "r", encoding="utf-8") as html:
        plantilla_html = html.read()

    context = {
        "grouped_data": get_grouped_entries(bibtext.entries),
        "date": datetime.now().strftime("%B %d, %Y"),
    }
    render = Template(plantilla_html).render(data=context)
    styles = CSS(filename=css_path)
    pdf_as_bytes = HTML(
        string=render,
        base_url=templates_path,
    ).write_pdf(stylesheets=[styles])

    return pdf_as_bytes
