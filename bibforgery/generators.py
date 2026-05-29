from .parser import (
    parse_bibtex,
    process_entries_as_json,
    process_entries_as_text,
    get_grouped_entries,
)
from .tools import fetch_citing_articles
from .libjabbrev2 import jabbreviation2
from enum import Enum

from jinja2 import Template
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
import os, io, json


class CitationStyle(Enum):
    ACS = 1
    APS = 2


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


from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    r_id = part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True
    )

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    rPr = OxmlElement("w:rPr")

    rStyle = OxmlElement("w:rStyle")
    rStyle.set(qn("w:val"), "Hyperlink")
    rPr.append(rStyle)

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    rPr.append(color)

    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)

    run = OxmlElement("w:r")
    run.append(rPr)

    t = OxmlElement("w:t")
    t.text = text
    run.append(t)

    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def set_paragraph_spacing(para, before=0, after=4, line=None):
    pf = para.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = line


def add_hanging_paragraph(doc, number_text, body_runs, indent_cm=0.0, number_width_cm=0.9):
    """
    Párrafo con numeración manual y sangría francesa (hanging indent).
    number_text : str  — p.ej. "[47]"
    body_runs   : list of (text, bold, italic, font_size_pt)
    """
    para = doc.add_paragraph()
    set_paragraph_spacing(para, before=0, after=5)

    left = Cm(indent_cm + number_width_cm)
    hanging = Cm(number_width_cm)

    pf = para.paragraph_format
    pf.left_indent = left
    pf.first_line_indent = -hanging

    # número
    run_num = para.add_run(number_text + "\t")
    run_num.font.name = "Arial"
    run_num.font.size = Pt(11)
    run_num.font.bold = False

    # set tab stop at number_width_cm so text aligns after the number
    pPr = para._p.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "left")
    # convert cm to twips (1 cm ≈ 567 twips)
    tab.set(qn("w:pos"), str(int(number_width_cm * 567)))
    tabs.append(tab)
    pPr.append(tabs)

    for text, bold, italic, size in body_runs:
        r = para.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(size or 11)
        r.font.bold = bold
        r.font.italic = italic

    return para


def add_citation_formatted(doc, entry, global_index, abbreviated=True, extra_indent=False):
    """
    Reemplaza add_citation con formato ACS-style y numeración inversa visible.
    Ajusta los campos a lo que devuelva tu entry de Scopus.
    """
    indent_cm = 0.8 if extra_indent else 0.0

    authors_raw = entry.get("dc:creator", "") or entry.get("authors", "")
    title = entry.get("dc:title", "")
    journal = entry.get("prism:publicationName", "")
    volume = entry.get("prism:volume", "")
    issue = entry.get("prism:issueIdentifier", "")
    pages = entry.get("prism:pageRange", "") or entry.get("page-range", "")
    year = (entry.get("prism:coverDate", "") or "")[:4]
    doi = entry.get("prism:doi", "")

    # formatear autores abreviados
    if abbreviated and authors_raw:
        authors = authors_raw  # aquí aplica tu lógica de abreviación existente
    else:
        authors = authors_raw

    number_text = f"[{global_index}]"
    journal = jabbreviation2(journal) if abbreviated else journal

    # construir runs: (text, bold, italic, pt)
    runs = []
    if authors:
        runs.append((authors + " ", False, False, 11))
    if title:
        runs.append((title + ". ", False, False, 11))
    if journal:
        runs.append((journal, False, True, 11))  # journal en cursiva
    if volume:
        runs.append((f" {volume}", True, False, 11))  # volumen en negrita
    if issue:
        runs.append((f"({issue})", False, False, 11))
    if pages:
        runs.append((f", {pages}", False, False, 11))
    if year:
        runs.append((f" ({year})", False, False, 11))

    para = add_hanging_paragraph(doc, number_text, runs, indent_cm=indent_cm)

    if doi:
        r_prefix = para.add_run(". DOI: ")
        r_prefix.font.name = "Arial"
        r_prefix.font.size = Pt(10)

        add_hyperlink(para, doi, f"https://doi.org/{doi}")


def generate_docx(json_input, output) -> None:
    data = json.loads(json_input)
    entries = data.get("search-results", {}).get("entry", [])

    def get_year(e):
        d = e.get("prism:coverDate", "0000")
        try:
            return int(d[:4])
        except (ValueError, TypeError):
            return 0

    sorted_entries = sorted(entries, key=get_year, reverse=True)
    total = len(sorted_entries)

    doc = Document()

    # estilos base
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    # márgenes y tamaño
    section = doc.sections[0]
    section.page_height = Inches(11)
    section.page_width = Inches(8.5)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)

    # título
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.paragraph_format.space_after = Pt(16)
    r = title_para.add_run("Publications")
    r.font.bold = True
    r.font.size = Pt(12)
    r.font.name = "Arial"

    for i, entry in enumerate(sorted_entries):
        global_index = total - i
        cited_count = int(entry.get("citedby-count", 0))
        eid = entry.get("eid", "")
        short_title = entry.get("dc:title", "")[:55]
        print(f" [{global_index:>3}/{total}] {short_title}... (citado: {cited_count}) -> EID: {eid}")

        add_citation_formatted(doc, entry, global_index, abbreviated=True)

        if cited_count > 0 and eid:
            cites_data = fetch_citing_articles(
                eid,
                "db914ab9d5f084e447fa55aa8c441393",
                "d7e05f3ac9d63a6d51b9170681078e96",
            )
            cites = cites_data.get("search-results", {}).get("entry", [])

            label_para = doc.add_paragraph()
            label_para.paragraph_format.left_indent = Cm(0.8)
            label_para.paragraph_format.space_before = Pt(3)
            label_para.paragraph_format.space_after = Pt(2)
            r = label_para.add_run(f"Cited by ({len(cites)}):")
            r.font.bold = True
            r.font.size = Pt(11)
            r.font.name = "Arial"

            for j, cite_entry in enumerate(cites, start=1):
                add_citation_formatted(doc, cite_entry, j, abbreviated=True, extra_indent=True)

        # separador visual entre entradas principales
        sep = doc.add_paragraph()
        sep.paragraph_format.space_before = Pt(0)
        sep.paragraph_format.space_after = Pt(4)

    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    print(f"\n[Info] — DOCX creado: {output_path} ({total} artículos)")
