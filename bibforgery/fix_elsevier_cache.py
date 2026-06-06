from bibforgery.tools import load_cache, save_cache
from lxml import etree
import re, time, requests


def _elsevier_title_to_html(xml: str) -> str:
    # Namespaces comunes de Elsevier/MathML
    NS = {
        "ce": "http://www.elsevier.com/xml/common/dtd",
        "mml": "http://www.w3.org/1998/Math/MathML",
    }

    # Parser tolerante a namespaces sin declaración explícita
    # Inyectamos las declaraciones si faltan
    if "xmlns" not in xml:
        xml = xml.replace(
            "<ce:title",
            '<ce:title xmlns:ce="http://www.elsevier.com/xml/common/dtd"'
            ' xmlns:mml="http://www.w3.org/1998/Math/MathML"',
            1,
        ).replace(
            "<mml:math",
            "<mml:math",  # ya cubierto por el xmlns inyectado arriba
        )

    root = etree.fromstring(xml.encode())

    def mathml_to_text(node):
        """Convierte un nodo MathML a texto/HTML plano de forma recursiva."""
        tag = etree.QName(node).localname
        children_text = "".join(mathml_to_text(c) for c in node)

        if tag == "msup":
            # msup: base + exponente → base<sup>exp</sup>
            parts = [mathml_to_text(c) for c in node]
            base = parts[0] if len(parts) > 0 else ""
            exp = parts[1] if len(parts) > 1 else ""
            return f"{base}<sup>{exp}</sup>"
        elif tag == "msub":
            parts = [mathml_to_text(c) for c in node]
            base = parts[0] if len(parts) > 0 else ""
            sub = parts[1] if len(parts) > 1 else ""
            return f"{base}<sub>{sub}</sub>"
        elif tag == "mfrac":
            parts = [mathml_to_text(c) for c in node]
            num = parts[0] if len(parts) > 0 else ""
            den = parts[1] if len(parts) > 1 else ""
            return f"({num}/{den})"
        elif tag == "mrow":
            return children_text
        elif tag in ("mi", "mn", "mo", "mtext"):
            return node.text or ""
        elif tag == "math":
            return children_text
        else:
            # Fallback: concatenar texto de hijos
            return children_text + (node.text or "")

    def walk(node):
        tag = etree.QName(node).localname
        result = node.text or ""

        for child in node:
            child_tag = etree.QName(child).localname

            if child_tag == "math":
                # Nodo MathML: convertir a representación HTML
                result += mathml_to_text(child)
            elif child_tag == "inf":
                result += f"<sub>{walk(child)}</sub>"
            elif child_tag == "sup":
                result += f"<sup>{walk(child)}</sup>"
            elif child_tag in ("italic", "it"):
                result += f"<i>{walk(child)}</i>"
            elif child_tag == "bold":
                result += f"<b>{walk(child)}</b>"
            else:
                result += walk(child)

            result += child.tail or ""

        return result

    raw = walk(root).strip()
    normalized = re.sub(r"[\r\n]+", " ", raw)  # elimina saltos de línea
    normalized = re.sub(r" {2,}", " ", normalized)  # colapsa espacios múltiples
    normalized = re.sub(r" ,", ",", normalized)  # limpia espacios antes de coma
    return normalized.strip()


def _get_elsevier_ce_title(doi: str, api_key: str, inst_token: str) -> str | None:
    url = f"https://api.elsevier.com/content/article/doi/{doi}?httpAccept=text/xml"

    response = requests.get(
        url,
        headers={
            "X-ELS-APIKey": api_key,
            "X-ELS-Insttoken": inst_token,
            "Accept": "application/vnd.crossref.unixsd+xml",
        },
        timeout=30,
    )

    response.raise_for_status()

    root = etree.fromstring(response.content)

    ns = {
        "ja": "http://www.elsevier.com/xml/ja/dtd",
        "ce": "http://www.elsevier.com/xml/common/dtd",
    }

    title = root.xpath(
        "//ja:article/ja:head/ce:title",
        namespaces=ns,
    )

    if not title:
        return None

    return etree.tostring(
        title[0],
        encoding="unicode",
        method="xml",
    )


def _needs_fix(title: str) -> bool:
    return re.search(r"[A-Za-z]\d", title) is not None and "<sub>" not in title and "<sup>" not in title


def fix_elsevier_doi_in_cache(
    api_key: str,
    inst_token: str,
    limit: int | None = None,
    sleep_seconds: float = 0.4,
    dry_run=False,
):
    cache = load_cache()

    dois = [doi for doi, title in cache.items() if doi.startswith("10.1016/") and _needs_fix(title)]

    print(f"{min(len(dois), limit or len(dois))} DOIs para corregir")

    fixed = 0
    for i, doi in enumerate(dois, start=1):
        if limit is not None and i > limit:
            break

        try:
            print(f"[{i}/{len(dois)}] {doi}")

            title_xml = _get_elsevier_ce_title(
                doi,
                api_key,
                inst_token,
            )

            if not title_xml:
                print("  Sin título XML")
                continue

            html_title = _elsevier_title_to_html(title_xml)

            if html_title:
                cache[doi] = html_title
                fixed += 1
                print(f"  OK -> {html_title}")

            time.sleep(sleep_seconds)

        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(max(1, sleep_seconds))

    if not dry_run:
        save_cache(cache)

    print(f"Corregidos: {fixed}")
    print("Cache guardado")
