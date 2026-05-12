from bibtexparser.library import Library
from bibtexparser.model import Field, Entry
from collections.abc import MutableSequence
from collections import defaultdict
from .libjabbrev2 import jabbreviation2
import bibtexparser


def parse_bibtex(input) -> Library:
    bibtext = bibtexparser.parse_string(input)
    if bibtext.failed_blocks:
        print(f"[Warning] — Found {len(bibtext.failed_blocks)} Failed Blocks")
        for block in bibtext.failed_blocks:
            print(f"\tLine: {block.start_line}")
            print(f"\tError: {block.error}")
    return bibtext


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


def get_authors_list(author_field: Field):
    authors = author_field.value.split(" and ")
    author_list = []
    for a in authors:
        parts = a.split(",")
        family = parts[0].strip()
        names = parts[1].strip()
        author_list.append(
            {
                "family": family,
                "names": names,
            }
        )
    return author_list


def get_grouped_entries(bib_entries: MutableSequence[Entry]):
    """
    Args:
        bib_entries (MutableSequence[Entry]): secuencia de entradas generada por bibtexparser

    Clasifica por año una secuencia de entradas
    generadas por bibtexparser. Si una entrada no
    tiene año la clasifica como "Sin Año".
    """

    def extract_year(entry):
        y = entry.get("year")
        try:
            return int(y.value) if y else 0
        except (ValueError, AttributeError):
            return 0

    sorted_entries = sorted(bib_entries, key=extract_year, reverse=True)
    total_papers = len(sorted_entries)

    grouped = defaultdict(list)
    for i, entry in enumerate(sorted_entries):
        global_index = total_papers - i

        year_field = entry.get("year")
        year = year_field.value if year_field else "Sin Año"

        citation_html = process_single_entry_as_html(entry, global_index)
        grouped[year].append(citation_html)

    sorted_years = sorted(grouped.keys(), reverse=True)
    return [(y, grouped[y]) for y in sorted_years]


def process_single_entry_as_html(entry: Entry, index: int, use_abbreviation=True):
    """
    Args:
        entry (Entry): Entrada generada por bibtexparser

    Returns:
        String de HTML de una cita bibliográfica
        a partir de una entrada en formato bibtex
    """

    author_string = entry.get("author")
    author_string = transform_authors(author_string)

    journal_key = 'journal_abbrev' if use_abbreviation else 'journal'
    journal_string = entry.get(journal_key)

    title_string = entry.get("title")
    
    year, v, n, p, d = (
        entry.get("year"),
        entry.get("volume"),
        entry.get("number"),
        entry.get("pages"),
        entry.get("doi"),
    )

    res = f'{author_string} <span style="font-style: italic;">{title_string.value}</span>. {journal_string}'
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

    return f"""
    <div style="display: flex; margin-bottom: 8px;">
        <div style="min-width: 30px; font-weight: bold;">{index}.</div>
        <div style="flex: 1;">{res}</div>
    </div>
    """


def process_entries_as_text(bib_entries: MutableSequence[Entry], use_abbreviations=True):
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

        journal_key = 'journal_abbrev' if use_abbreviations else 'journal'
        journal_string = entry.get(journal_key)

        title,  year, v, n, p, d = (
            entry.get("title"),
            entry.get("year"),
            entry.get("volume"),
            entry.get("number"),
            entry.get("pages"),
            entry.get("doi"),
        )

        res = f"{author_string} {title.value}. {journal_string} {year.value}"
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
            "authors": get_authors_list(entry.get("author")),
            "title": entry.get("title").value if entry.get("title") else "",
            "year": int(entry.get("year").value) if entry.get("year") else None,
            "journal": entry.get("journal").value if entry.get("journal") else "",
            "journal_abbrev": entry.get("journal_abbrev").value if entry.get("journal") else "",
            "doi": entry.get("doi").value if entry.get("doi") else None,
            "volume": entry.get("volume").value if entry.get("volume") else "",
            "number": entry.get("number").value if entry.get("number") else "",
            "pages": entry.get("pages").value if entry.get("pages") else "",
            "citedby-count": entry.get("citedby-count"),
        }
        yield data


class CitationStrategy:
    def __init__(self, entry: Entry):
        self.entry = entry

    def html(self):
        raise NotImplementedError

    def text(self):
        raise NotImplementedError


class APSCitation(CitationStrategy):
    def formatAuthors(self, author_field: Entry):
        authors = author_field.value.split(" and ")
        author_list = []
        for a in authors:
            parts = a.split(",")
            family = parts[0].strip()
            names = parts[1].strip().split(" ")
            initials = ""
            for n in names:
                initials += f"{n[0]}."
            author_list.append(f"{initials} {family}")

        if len(author_list) == 1:
            return author_list[0]

        result = ", ".join(author_list[:-1]) + " and " + author_list[-1]
        return result

    def html(self):
        author_string = self.entry.get("author")
        authors = self.formatAuthors(author_string)

        journal_string = self.entry.get("journal")
        journal_abb = jabbreviation2(journal_string.value)

        title, year, v, n, p, d = (
            self.entry.get("title"),
            self.entry.get("year"),
            self.entry.get("volume"),
            self.entry.get("number"),
            self.entry.get("pages"),
            self.entry.get("doi"),
        )

        res = f'{authors}, {title.value}, <span style="font-style: italic;">{journal_abb}</span>.'
        if v or n or p:
            res += ","
            if v:
                res += f' <span style="font-weight: bold;">{v.value}</span>'
            if n:
                res += f"({n.value})"
            if p:
                res += f", {p.value}"
        if year:
            res += f" ({year.value})."
        # if d:
        #     res += f'. DOI: <a href="https://doi.org/{d.value}" target="_blank" rel="noopener noreferrer" style="color: #0563C1; text-decoration: underline;">https://doi.org/{d.value}</a>'

        return res
