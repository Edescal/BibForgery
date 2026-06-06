#!/usr/bin/python3 -u
from colorama import Fore, Style, init
from dotenv import load_dotenv
from pathlib import Path
from .tools import (
    fetch_papers_by_author,
    fetch_citing_articles,
    get_data_from_file,
    load_cache,
    get_cache_info,
    clean_crossref_to_html,
)
from .fix_elsevier_cache import fix_elsevier_doi_in_cache
from .generators import generate_full_json, generate_docx, generate_pdf
from .bibtex import dict_to_bibtex, generate_txt
import argparse, os, json

init()


def dump_bytes_to_file(filepath: str, data: bytes | None, extension: str) -> None:
    if data is None:
        return

    path = Path(filepath)
    if not path.suffix == f".{extension}":
        path = path.with_suffix(f".{extension}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    print(f"{Fore.GREEN}[Info] — Archivo {extension} creado: {path}{Style.RESET_ALL}")


def dump_json_to_file(filepath: str, data, silent=False) -> None:
    path = Path(filepath)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"{path} es un directorio")

    if not path.suffix == ".json":
        path = path.with_suffix(".json")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if not silent:
        print(f"{Fore.GREEN}[Info] — Archivo json creado: {path}{Style.RESET_ALL}")


def resolve_name(prefix, name, extension):
    return Path(f"{prefix}/{name}.{extension}")


def handle_fetch(args):
    ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
    ELSEVIER_INST_TOKEN = os.getenv("ELSEVIER_INSTTOKEN")

    author_papers = fetch_papers_by_author(
        args.scopus_id,
        ELSEVIER_API_KEY,
        ELSEVIER_INST_TOKEN,
        crossref_title=args.crossref,
    )

    output_name = args.name if args.name else args.scopus_id
    base_input_file = resolve_name("output", f"{output_name}_papers", "json")
    dump_json_to_file(base_input_file, author_papers)
    print(f"  {Fore.GREEN}Listo: {base_input_file} {Style.RESET_ALL}")

    if args.full:
        print("\n Artículos citados:")

        def get_year(e):
            d = e.get("prism:coverDate", "0000")
            try:
                return int(d[:4])
            except (ValueError, TypeError):
                return 0

        entries = author_papers.get("papers", [])
        sorted_entries = sorted(entries, key=get_year, reverse=True)
        total = len(sorted_entries)

        for i, entry in enumerate(sorted_entries):
            global_index = total - i
            cited_count = int(entry.get("citedby-count", 0))
            eid = entry.get("eid", "")
            short_title = entry.get("dc:title", "")[:55]
            print(f"  [{global_index:>3}/{total}] {short_title}... (citado: {cited_count}) -> EID: {eid}")

            if cited_count > 0 and eid:
                cites_data = fetch_citing_articles(
                    eid,
                    ELSEVIER_API_KEY,
                    ELSEVIER_INST_TOKEN,
                    crossref_title=args.crossref,
                )
                citedby_json_filename = resolve_name(f"output/{output_name}", f"{output_name}_{eid}_citedby", "json")
                dump_json_to_file(citedby_json_filename, cites_data, True)
                print(f"  {Fore.GREEN}Listo: {citedby_json_filename} {Style.RESET_ALL}")


def handle_export(args):
    if args.format == "word" or args.format == "docx":
        docx = generate_docx(
            args.name,
            include_citations=args.full,
            citation_style=1 if args.style.lower() == "acs" else 2,
        )
        dump_bytes_to_file(args.output, docx, "docx")

    elif args.format == "pdf":
        pdf_as_bytes = generate_pdf(
            args.name,
            include_citations=args.full,
            citation_style=1 if args.style.lower() == "acs" else 2,
        )
        dump_bytes_to_file(args.output, pdf_as_bytes, "pdf")

    elif args.format == "text":
        input_file = resolve_name("output", f"{args.name}", "bib")
        raw_data = get_data_from_file(input_file)
        text_as_bytes = generate_txt(raw_data)
        dump_bytes_to_file(args.output, text_as_bytes, "txt")

    elif args.format == "bib":
        input_file = resolve_name("output", f"{args.name}_papers", "json")
        raw_data = get_data_from_file(input_file)
        json_data = json.loads(raw_data)
        bibtex_data = dict_to_bibtex(json_data)
        dump_bytes_to_file(args.output, bibtex_data, "bib")

    elif args.format == "json":
        json_data = generate_full_json(args.name, include_citations=args.full)
        dump_json_to_file(args.output, json_data)


def handle_list(args):
    output_path = Path(f"output").resolve()
    output_path_files = list(output_path.glob("*_papers.json"))

    authors_count = len(output_path_files)
    print(f"{Fore.YELLOW + Style.BRIGHT}Información de los Autores Recopilados ({authors_count}): {Style.RESET_ALL}")

    for file in output_path_files:
        paper_count = 0
        with file.open("r", encoding="utf-8") as f:
            paper_data = json.load(f)
            papers = paper_data.get("papers", [])
            paper_count = len(papers)

        og_name = file.name.removesuffix("_papers.json")
        words = og_name.split("_")
        capitalized = [w.capitalize() for w in words]
        name = " ".join(capitalized)

        paper_citations = output_path / og_name
        if paper_citations.is_dir():
            subfiles = paper_citations.glob(f"{og_name}_*_citedby.json")
            count = len(list(subfiles))
        else:
            count = 0

        print(f"Nombre: {name:<15.15} Papers: {str(paper_count):<8.4} Papers con citas: {str(count):<4.4}")


def handle_recache(args):
    filename = f"output/{args.name}_papers.json"
    papers_file = Path(filename).resolve()
    with papers_file.open("r", encoding="utf-8") as file:
        paper_data = json.load(file)
        papers = paper_data.get("papers", [])

        def recache_load_paper(item):
            doi = item.get("prism:doi", None)
            xml_title = cache.get(doi, None)
            if xml_title:
                clean_title = clean_crossref_to_html(xml_title)
                item["xml:title"] = clean_title

        cache = load_cache()
        for item in papers:
            recache_load_paper(item)

            if not args.full:
                continue

            eid = item.get("eid", None)
            citedby_count = item.get("citedby-count", 0)
            if not eid or citedby_count == 0:
                continue

            citedby_path = Path(f"output/{args.name}/").resolve()
            if not citedby_path.is_dir():
                continue

            citedby_files = citedby_path.glob(f"{args.name}_*_citedby.json")
            for c_f in citedby_files:
                with c_f.open("r", encoding="utf-8") as f:
                    print(f.name)
                    c_paper_data = json.load(f)
                    c_papers = c_paper_data.get("papers", [])
                    for c_item in c_papers:
                        recache_load_paper(c_item)

                    dump_json_to_file(c_f.absolute(), c_paper_data, True)
            print(f"{Fore.YELLOW}[Info] — Actualizado {eid} desde caché{Style.RESET_ALL}")

    dump_json_to_file(papers_file, paper_data, False)
    print(f"{Fore.GREEN}[Info] — Datos para {args.name} actualizados desde caché{Style.RESET_ALL}")


def handle_cache_info(args):
    print(f"\n{Style.BRIGHT}Cache Information{Style.RESET_ALL}")
    print("─" * 19)
    res = get_cache_info()
    for key, val in res.items():
        print(f"{Fore.YELLOW}{key:<18.17}{Style.RESET_ALL}| {Fore.CYAN}{val}{Style.RESET_ALL}")


def handle_cache_fix(args):
    ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
    ELSEVIER_INST_TOKEN = os.getenv("ELSEVIER_INSTTOKEN")
    fix_elsevier_doi_in_cache(
        api_key=ELSEVIER_API_KEY,
        inst_token=ELSEVIER_INST_TOKEN,
        limit=args.limit,
        sleep_seconds=0.3,
        dry_run=args.dry_run,
    )


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("scopus_id", help="ID de Scopus del autor")
    fetch.add_argument("-f", "--full", action="store_true", help="Incluye papers que han citado los papers")
    fetch.add_argument("-c", "--crossref", action="store_true", help="Busca títulos formateados desde Crossref")
    fetch.add_argument("-n", "--name", type=str, help="Nombre del registro que se creará")
    fetch.set_defaults(func=handle_fetch)

    format_choices = ["text", "json", "pdf", "docx", "word", "bib"]

    export = subparsers.add_parser("export")
    export.add_argument("name", type=str, help="Nombre del registro de origen")
    export.add_argument("-f", "--format", required=True, choices=format_choices, help="Formato de salida")
    export.add_argument("-o", "--output", required=True, help="Nombre del archivo de salida")
    export.add_argument("--style", choices=["aps", "acs"], default="acs")
    export.add_argument("--full", action="store_true", help="Incluye papers que han citado los papers")
    export.set_defaults(func=handle_export)

    db = subparsers.add_parser("db")
    db_subp = db.add_subparsers(dest="action", required=True)

    db_subp_list = db_subp.add_parser("list")
    db_subp_list.set_defaults(func=handle_list)

    db_subp_cache_info = db_subp.add_parser("cacheinfo")
    db_subp_cache_info.set_defaults(func=handle_cache_info)

    db_subp_cache_info = db_subp.add_parser("cachefix")
    db_subp_cache_info.add_argument("-l", "--limit", type=int, default=None, help="Número de elementos a procesar")
    db_subp_cache_info.add_argument("--dry-run", action="store_true", help="Realizar sin guardar cambios")
    db_subp_cache_info.set_defaults(func=handle_cache_fix)

    db_subp_recache = db_subp.add_parser("recache")
    db_subp_recache.add_argument("-n", "--name", required=True, type=str, help="Nombre del registro de origen")
    db_subp_recache.add_argument("--full", action="store_true", help="Incluye papers que han citado los papers")
    db_subp_recache.set_defaults(func=handle_recache)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
