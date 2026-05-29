from .libjabbrev2 import jabbreviation2
from pathlib import Path
from lxml import etree
import requests, time, re

def clean_crossref_title(title: str) -> str:
    if not title:
        return ''
    title = re.sub(r"\s*\n\s*", " ", title)
    title = re.sub(r">\s+<", "><", title)
    title = re.sub(r"\s*(</?(?:sub|sup|i|b)>)\s*", r"\1", title)
    title = re.sub(r"\s{2,}", " ", title)
    title = re.sub(r"(</(?:sub|sup|i|b)>)\s*([A-Za-z])", r"\1 \2", title)
    title = re.sub(r"(\d)([A-Za-z])", r"\1 \2", title)

    return title.strip()

def get_citedby_count_from_xml(root):
    node = root.find(".//{*}citedby-count")
    return node.text if node is not None else "0"


def get_title_from_xml(root):
    title = root.find(".//{*}titletext")
    if title is None:
        return ""
    html = etree.tostring(title, encoding="unicode", method="html")
    start = html.find(">") + 1
    end = html.rfind("</")
    title = html[start:end]
    title = title.replace("<inf>", "<sub>")
    title = title.replace("</inf>", "</sub>")
    title = re.sub(r"\s+(<sub>)", r"\1", title)
    title = re.sub(r"\s+(<sup>)", r"\1", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def get_data_from_file(input) -> str:
    input_path = Path(input).resolve()
    if not input_path.exists():
        print(f"Error: No se encuentra el archivo de entrada {input_path}")
        return
    with open(input_path, "r", encoding="utf-8") as file:
        data = file.read()
    return data


def data_to_bibtex(data) -> str:
    entries = data.get("search-results", {}).get("entry", [])
    full_bib = ""

    for entry in entries:
        alt_title = None
        title = entry.get("dc:title", "")
        authors = entry.get("author", [])
        author_list = [f"{a.get('surname','')}, {a.get('given-name','')}".strip(", ") for a in authors]
        authors_str = " and ".join(author_list) if author_list else entry.get("dc:creator", "Unknown")

        journal = entry.get("prism:publicationName", "")
        date = entry.get("prism:coverDate", "0000-00-00")
        year = date[:4]
        month = date[5:7] if len(date) >= 7 else ""
        day = date[8:10] if len(date) >= 10 else ""
        volume = entry.get("prism:volume", "")
        issue = entry.get("prism:issueIdentifier", "")
        pages = entry.get("prism:pageRange", "")
        eid = entry.get("eid", "")
        citedby_count = int(entry.get('citedby-count', "0"))
        doi = entry.get("prism:doi", "")
        if doi:
            crossref_data = fetch_crossref_from_doi(doi, 'contact@watoc2028.org')
            if crossref_data:
                alt_title = crossref_data.get('message', {}).get('title', [''])[0]
                alt_title = clean_crossref_title(alt_title)
                time.sleep(0.3)

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
        bib += f"  title = {{{alt_title if len(alt_title) > (len(title)) else title}}},\n"
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


def fetch_crossref_from_doi(doi: str, mailto: str):
    """
    Get metadata from Crossref using DOI
    """
    url = f"https://api.crossref.org/works/{doi}"

    headers = {"User-Agent": f"BibTool/1.0 (mailto:{mailto})"}
    params = {"mailto": mailto}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    return response.json()


def fetch_content_article(scopus_id, api_key="", inst_token=""):
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/xml",
    }

    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token

    print(f"Query for {scopus_id}")
    res = requests.get(f"https://api.elsevier.com/content/abstract/scopus_id/{scopus_id}", headers=headers)
    if res.status_code != 200:
        print("Error:", res.status_code, res.text)
        return None

    root = etree.fromstring(res.content)

    print(f" — Fetched")
    print(f"   X-RateLimit-Limit: {res.headers.get('X-RateLimit-Limit', '')}")
    print(f"   X-RateLimit-Remaining: {res.headers.get('X-RateLimit-Remaining', '')}")
    time.sleep(0.2)
    return root






def fetch_papers_by_author(author_id: str, api_key="", inst_token="", max_results=500):
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
        "search-results": {
            "entry": all_entries,
        },
    }


def fetch_citing_articles(eid: str, api_key="", inst_token="", max_results=500):
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
        "search-results": {
            "entry": all_entries,
        },
    }
