from .parser import parse_bibtex, process_entries_as_json, process_entries_as_text, get_grouped_entries
from jinja2 import Template
from datetime import datetime
import os, io, json


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


def generate_json(input) -> bytes:
    """
    Genera citas en formato JSON a partir
    de un archivo en formato Bibtex y lo
    guarda en un archivo

    Args:
        input (string): Archivo de entrada.
        output (string): Archivo de salida.
    """
   
    bibtext = parse_bibtex(input)

    buffer = io.BytesIO()
    buffer.write(b"[")
    yielder = process_entries_as_json(bibtext.entries)
    try:
        first = next(yielder)
        buffer.write(json.dumps(first, separators=(",", ":"), ensure_ascii=False).encode('utf-8'))
        for item in yielder:
            buffer.write(b",")
            buffer.write(json.dumps(item, separators=(",", ":"), ensure_ascii=False).encode('utf-8'))
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
