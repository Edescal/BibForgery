from bs4 import BeautifulSoup, NavigableString, Tag
from pathlib import Path
import requests, time, re, json

CACHE_FILE = Path("crossref_cache.json")


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


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
    ELEMENT_RE = re.compile(r"^[A-Z][a-z]?$")

    soup = BeautifulSoup(title, "html.parser")

    tokens = []

    def walk(node):
        if isinstance(node, NavigableString):
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text:
                tokens.append(("text", text))
            return

        if not isinstance(node, Tag):
            return

        if node.name == "sub":
            text = re.sub(r"\s+", "", node.get_text())
            tokens.append(("sub", f"<sub>{text}</sub>"))
            return

        if node.name == "sup":
            text = re.sub(r"\s+", "", node.get_text())
            tokens.append(("sup", f"<sup>{text}</sup>"))
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

        # B + <sub>10</sub>
        if kind in {"sub", "sup"}:
            join = True

        # </sub>H
        elif prev_kind in {"sub", "sup"} and ELEMENT_RE.match(value):
            join = True

        if join:
            result.append(value)
        else:
            result.append(" ")
            result.append(value)

        prev_kind = kind

    html = "".join(result)

    html = re.sub(r"\s+", " ", html)
    html = re.sub(r"\(\s+", "(", html)
    html = re.sub(r"\s+\)", ")", html)

    return html.strip()


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
        print(f"   X-RateLimit-Limit: {res.headers.get('X-RateLimit-Limit', '')}")
        print(f"   X-RateLimit-Remaining: {res.headers.get('X-RateLimit-Remaining', '')}")
        time.sleep(0.2)

        next_limit = start + count
        if (next_limit) > max_results:
            count = max_results - start
        start += count

        if start >= total or start >= max_results:
            break

    return {
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
        print(f"  Fetching {eid}", end="")
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

        print(f" — Downloaded: {len(all_entries)}/{total}")
        print(f"   X-RateLimit-Limit: {res.headers.get('X-RateLimit-Limit', '')}")
        print(f"   X-RateLimit-Remaining: {res.headers.get('X-RateLimit-Remaining', '')}")
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
                "surname": author.get("surname"),
                "given-name": author.get("given-name"),
                "initials": author.get("initials"),
            }
            for author in entry.get("author", [])
        ]

        if not item["prism:doi"]:
            print(f"  [Warn] Skip better title for {item['eid']}: No DOI included.")

        elif get_better_title:
            doi = item["prism:doi"]
            title = item["dc:title"]
            if doi in cache:
                # print(f"  [Info] Fetching better title from cache for {doi}")
                item["xml:title"] = clean_crossref_to_html(cache[doi])

            else:
                print(f"  [Info] Fetching better title from crossref for {doi}")
                title = get_title_from_crossref(doi, "contact@watoc2028.org")
                if title:
                    item["xml:title"] = clean_crossref_to_html(title)
                    cache[doi] = title
                    save_cache(cache)
                time.sleep(0.3)

        data.append(item)

    return data
