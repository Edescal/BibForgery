from bs4 import BeautifulSoup, NavigableString, Tag
from pathlib import Path
import requests, time, re, json
from datetime import datetime
from platformdirs import user_cache_dir
from colorama import Style, init, Fore
from enum import IntFlag, auto
from typing import Any

init()

CACHE_DIR = Path(user_cache_dir("bibforgery"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "crossref_cache.json"


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_cache_info() -> dict:
    info = {
        "cache_dir": str(CACHE_DIR.resolve()),
        "cache_file": str(CACHE_FILE.resolve()),
        "cache_dir_exists": CACHE_DIR.exists(),
        "cache_file_exists": CACHE_FILE.exists(),
    }

    if not CACHE_FILE.exists():
        info.update(
            {
                "entries": 0,
                "size_bytes": 0,
                "last_modified": None,
            }
        )
        return info

    stat = CACHE_FILE.stat()

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            cache = json.load(f)

        info.update(
            {
                "entries": len(cache),
                "size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "valid": True,
            }
        )

    except Exception as e:
        info.update(
            {
                "entries": None,
                "size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "valid": False,
                "error": str(e),
            }
        )

    return info


def get_data_from_file(input) -> str:
    input_path = Path(input).resolve()
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: No se encuentra el archivo de entrada {input_path}")
        return None
    with open(input_path, "r", encoding="utf-8") as file:
        data = file.read()
    return data


def get_title_from_crossref(doi: str, mailto: str):
    url = f"https://api.crossref.org/works/{doi}"

    headers = {"User-Agent": f"BibTool/1.0 (mailto:{mailto})"}
    params = {"mailto": mailto}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    data = response.json()
    title = data.get("message", {}).get("title", [""])[0]
    return title


def clean_crossref_to_html(title: str) -> str:
    # Después de sub/sup: pegar si es símbolo químico O puntuación conectora
    JOIN_AFTER_SUBSUP_RE = re.compile(r"^([A-Z][a-z]?(?=[^a-z]|$)|[\u2013\u2014\-/])")
    # Después de </tag> normal: pegar si empieza con puntuación conectora
    JOIN_AFTER_CLOSE_RE = re.compile(r"^[\u2013\u2014\-/]")
    # Después de close de wrapper sub/sup: pegar si empieza con letra o puntuación de fórmula
    JOIN_AFTER_SUBSUP_WRAPPER_RE = re.compile(r"^[A-Za-z\u2013\u2014\-/:(]")
    # Texto/token que debe pegarse al token anterior si ese era sub/sup o wrapper
    PUNCT_AFTER_FORMULA_RE = re.compile(r"^[:\u2013\u2014\-/,;.!?]")

    INLINE_TAGS = {
        "i": "i",
        "em": "i",
        "b": "b",
        "strong": "b",
        "u": "u",
        "s": "s",
        "strike": "s",
        "small": "small",
        "mark": "mark",
    }

    soup = BeautifulSoup(title, "html.parser")
    tokens = []

    def node_is_subsup_only(node: Tag) -> bool:
        """True si todos los hijos significativos son sub/sup (es un wrapper de fórmula)."""
        for child in node.children:
            if isinstance(child, NavigableString):
                if str(child).strip():
                    return False
            elif isinstance(child, Tag):
                if child.name in ("sub", "sup"):
                    continue
                if child.name in INLINE_TAGS and node_is_subsup_only(child):
                    continue
                return False
        return True

    def walk(node):
        if isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text:
                tokens.append(("text", text))
            return
        if not isinstance(node, Tag):
            return

        if node.name in ("sub", "sup"):

            def inner_html(n):
                if isinstance(n, NavigableString):
                    return re.sub(r"\s+", "", str(n))
                if not isinstance(n, Tag):
                    return ""
                if n.name in INLINE_TAGS:
                    tag_out = INLINE_TAGS[n.name]
                    return f"<{tag_out}>{''.join(inner_html(c) for c in n.children)}</{tag_out}>"
                return "".join(inner_html(c) for c in n.children)

            inner = "".join(inner_html(c) for c in node.children)
            tokens.append((node.name, f"<{node.name}>{inner}</{node.name}>"))
            return

        if node.name in INLINE_TAGS:
            tag_out = INLINE_TAGS[node.name]
            is_wrapper = node_is_subsup_only(node)
            open_kind = "open_subsup_wrapper" if is_wrapper else "open"
            close_kind = "close_subsup_wrapper" if is_wrapper else "close"
            tokens.append((open_kind, f"<{tag_out}>"))
            for child in node.children:
                walk(child)
            tokens.append((close_kind, f"</{tag_out}>"))
            return

        for child in node.children:
            walk(child)

    for child in soup.children:
        walk(child)

    result = []
    prev_kind = None

    for kind, value in tokens:
        if not result:
            result.append(value)
            prev_kind = kind
            continue

        join = False

        if kind in {"sub", "sup"}:
            # sub/sup siempre pega con lo anterior (H₂O: H pega con <sub>2</sub>)
            join = True

        elif kind == "open_subsup_wrapper":
            # <b><sub>4</sub></b> wrapper pega con el texto/token anterior (K<b>...)
            join = True

        elif kind == "open":
            # <i>, <b> normales: solo pegan si lo anterior ya estaba pegado (sub/sup/wrapper/open)
            # En texto normal: "Effect of <b>" → espacio normal
            join = prev_kind in {"sub", "sup", "open", "open_subsup_wrapper", "close_subsup_wrapper"}

        elif prev_kind == "open_subsup_wrapper":
            # justo después de abrir un wrapper → sin espacio (el sub viene dentro)
            join = True

        elif prev_kind == "open":
            # justo después de <i> o <b> normal → sin espacio con el primer hijo
            join = True

        elif kind in {"close", "close_subsup_wrapper"}:
            # nunca espacio antes del cierre de tag
            join = True

        elif prev_kind in {"sub", "sup"}:
            if JOIN_AFTER_SUBSUP_RE.match(value):
                # símbolo químico o guión/slash tras subíndice
                join = True
            elif PUNCT_AFTER_FORMULA_RE.match(value):
                # ":" u otra puntuación tras superíndice (<sup>–</sup>: …)
                join = True

        elif prev_kind == "close":
            if JOIN_AFTER_CLOSE_RE.match(value):
                # <i>n</i>-body → sin espacio
                join = True

        elif prev_kind == "close_subsup_wrapper":
            if JOIN_AFTER_SUBSUP_WRAPPER_RE.match(value):
                # <b><sub>4</sub></b>I → sin espacio (continuación de fórmula)
                join = True

        result.append("" if join else " ")
        result.append(value)
        prev_kind = kind

    html = "".join(result)
    html = re.sub(r"\s+", " ", html)
    html = re.sub(r"\(\s+", "(", html)
    html = re.sub(r"\s+\)", ")", html)
    return html.strip()


class CitationType(IntFlag):
    Autocitation = auto()
    A = auto()
    B = auto()


def get_citation_type(author_id: str, authors_set: set[str], cita: dict[str, Any]) -> CitationType:
    citing_authors = cita.get("author", [])
    current_set = set([a["authid"] for a in citing_authors])

    if author_id in current_set:
        return CitationType.Autocitation

    comparison = current_set & authors_set
    if len(comparison) > 0:
        return CitationType.B

    return CitationType.A


def filter_citations(author_id, authors_list: list, citation_target: CitationType, papers: list):
    if not author_id:
        return papers

    og_authors = [a["authid"] for a in authors_list]
    og_authors_set = set(og_authors)
    og_authors_set.discard(author_id)

    results = []
    for cita in papers:
        citation_type = get_citation_type(author_id, og_authors_set, cita)

        if citation_type & citation_target:
            results.append(cita)
            print(cita['dc:title'])

    return results


def fetch_papers_by_author(
    author_id: str,
    api_key="",
    inst_token="",
    max_results=500,
    crossref_title=False,
):
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
    }
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token

    iter = 1
    start = 0
    count = 25
    all_entries = []

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
        print(f"{Style.DIM}   X-RateLimit-Limit: {res.headers.get('X-RateLimit-Limit', '')} {Style.RESET_ALL}")
        print(f"{Style.DIM}   X-RateLimit-Remaining: {res.headers.get('X-RateLimit-Remaining', '')} {Style.RESET_ALL}")
        time.sleep(0.2)

        next_limit = start + count
        if (next_limit) > max_results:
            count = max_results - start
        start += count

        if start >= total or start >= max_results:
            break

    return {
        "authorid": f"{author_id}",
        "papers": process_scopus_response(all_entries, get_better_title=crossref_title),
    }


def fetch_citing_articles(
    eid: str,
    api_key="",
    inst_token="",
    max_results=500,
    crossref_title=False,
):
    headers = {"X-ELS-APIKey": api_key, "Accept": "application/json"}
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token

    all_entries = []
    start = 0
    count = 25

    while True:
        print(f"{Style.DIM}  [Info] Fetching citing papers for {eid}{Style.RESET_ALL}", end="")
        params = {
            "query": f"ref({eid})",
            "start": start,
            "count": count,
            "view": "COMPLETE",
            "sort": "-coverDate",
        }

        try:
            res = requests.get(
                "https://api.elsevier.com/content/search/scopus",
                headers=headers,
                params=params,
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"  [Warning] Error de red para EID {eid}: {e}")
            break

        if res.status_code != 200:
            print(f"  [Warning] API devolvió {res.status_code} para EID {eid}")
            break

        data = res.json()
        results = data.get("search-results", {})
        entries = results.get("entry", [])
        total = int(data["search-results"]["opensearch:totalResults"])

        # La API devuelve [{"error": "..."}] cuando no hay resultados
        if not entries or "error" in entries[0]:
            break

        all_entries.extend(entries)
        total = int(results.get("opensearch:totalResults", 0))
        start += count

        print(f"{Style.DIM} — Downloaded: {len(all_entries)}/{total}{Style.RESET_ALL}")
        print(f"{Style.DIM}   X-RateLimit-Limit: {res.headers.get('X-RateLimit-Limit', '')} {Style.RESET_ALL}")
        print(f"{Style.DIM}   X-RateLimit-Remaining: {res.headers.get('X-RateLimit-Remaining', '')} {Style.RESET_ALL}")
        time.sleep(0.2)

        if start >= total or start >= max_results:
            break

    return {
        "papers": process_scopus_response(all_entries, get_better_title=crossref_title),
    }


def process_scopus_response(entries, get_better_title=False):
    FIELDS = [
        "eid",
        "dc:title",
        "prism:publicationName",
        "prism:coverDate",
        "prism:volume",
        "prism:issueIdentifier",
        "prism:pageRange",
        "citedby-count",
        "prism:doi",
    ]

    data = []
    cache = None
    if get_better_title:
        cache = load_cache()

    for entry in entries:
        item = {field: entry.get(field) for field in FIELDS}

        item["author"] = [
            {
                "authid": author.get("authid"),
                "surname": author.get("surname"),
                "given-name": author.get("given-name"),
                "initials": author.get("initials"),
            }
            for author in entry.get("author", [])
        ]

        if not item["prism:doi"]:
            print(f"  [Warn] No DOI included for {item['eid']}")

        elif get_better_title:
            doi = item["prism:doi"]
            title = item["dc:title"]
            if doi in cache:
                print(f"{Style.DIM}  [Info] Fetching title from cache for {doi}{Style.RESET_ALL}")
                item["xml:title"] = clean_crossref_to_html(cache[doi])

            else:
                print(f"{Style.DIM}{Fore.YELLOW}  [Warning] Fetching title from Crossref for {doi}{Style.RESET_ALL}")
                title = get_title_from_crossref(doi, "contact@watoc2028.org")
                if title:
                    item["xml:title"] = clean_crossref_to_html(title)
                    cache[doi] = title
                    save_cache(cache)
                time.sleep(0.3)

        data.append(item)

    return data
