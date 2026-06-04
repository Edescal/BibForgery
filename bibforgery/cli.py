#!/usr/bin/python3 -u
from colorama import Fore, Style, init
from dotenv import load_dotenv
from pathlib import Path
from .tools import fetch_papers_by_author, fetch_citing_articles, get_data_from_file
from .bibtex import dict_to_bibtex, generate_txt
from .generators import generate_full_json, generate_docx, generate_pdf
import argparse, os, json

init()


def dump_json_to_file(data, output="output.json") -> None:
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_name(prefix, name, extension):
    return Path(f"{prefix}/{name}.{extension}")


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


def handle_fetch(args):
    ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
    ELSEVIER_INST_TOKEN = os.getenv("ELSEVIER_INSTTOKEN")

    base_data = fetch_papers_by_author(
        args.scopus_id,
        ELSEVIER_API_KEY,
        ELSEVIER_INST_TOKEN,
        crossref_title=args.crossref,
    )

    output_name = args.name if args.name else args.scopus_id
    base_input_file = resolve_name("output", f"{output_name}_papers", "json")
    dump_json_to_file(base_data, base_input_file)
    print(f"  {Fore.GREEN}Listo: {base_input_file} {Style.RESET_ALL}")

    if args.full:
        print("\n Artículos citados:")

        def get_year(e):
            d = e.get("prism:coverDate", "0000")
            try:
                return int(d[:4])
            except (ValueError, TypeError):
                return 0

        entries = base_data.get("papers", [])
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
                dump_json_to_file(cites_data, citedby_json_filename)
                print(f"  {Fore.GREEN}Listo: {citedby_json_filename} {Style.RESET_ALL}")


def handle_export(args):
    def dump_bytes_to_file(path, bytes):
        with open(path, "wb") as f:
            f.write(bytes)

    output_filename = args.output if args.output else args.name
    if args.format == "word" or args.format == "docx":
        docx = generate_docx(
            args.name,
            include_citations=args.full,
            citation_style=1 if args.style.lower() == "acs" else 2,
        )

        dump_bytes_to_file(resolve_name("output", output_filename, "docx"), docx)
        print(f"{Fore.GREEN}[Info] — Archivo docx creado: {output_filename}.docx {Style.RESET_ALL}")

    elif args.format == "pdf":
        pdf_as_bytes = generate_pdf(
            args.name,
            include_citations=args.full,
            citation_style=1 if args.style.lower() == "acs" else 2,
        )
        dump_bytes_to_file(resolve_name("output", output_filename, "pdf"), pdf_as_bytes)
        print(f"{Fore.GREEN}[Info] — Archivo PDF creado: {output_filename}.pdf {Style.RESET_ALL}")

    elif args.format == "text":
        input_file = resolve_name("output", f"{args.name}", "bib")
        raw_data = get_data_from_file(input_file)
        text_as_bytes = generate_txt(raw_data)

        dump_bytes_to_file(resolve_name("output", output_filename, "txt"), text_as_bytes)
        print(f"{Fore.GREEN}[Info] — Archivo txt creado: {output_filename}.txt {Style.RESET_ALL}")

    elif args.format == "bib":
        input_file = resolve_name("output", f"{args.name}_papers", "json")
        raw_data = get_data_from_file(input_file)
        json_data = json.loads(raw_data)
        bibtex_data = dict_to_bibtex(json_data)

        dump_bytes_to_file(resolve_name("output", output_filename, "bib"), bibtex_data)
        print(f"{Fore.GREEN}[Info] — Archivo BibTex creado: {output_filename}.bib {Style.RESET_ALL}")

    elif args.format == "json":
        json_data = generate_full_json(args.name, include_citations=args.full)
        
        dump_json_to_file(json_data, resolve_name("output", output_filename, "json"))
        print(f"{Fore.GREEN}[Info] — Archivo JSON creado: {output_filename}.json {Style.RESET_ALL}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command")

    db = subparsers.add_parser("db")
    db_subp = db.add_subparsers(dest="action", required=True)

    db_subp_list = db_subp.add_parser("list")
    db_subp_list.set_defaults(func=handle_list)

    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("scopus_id", help="ID de Scopus del autor")
    fetch.add_argument("-f", "--full", action="store_true", help="Incluye papers que han citado los papers")
    fetch.add_argument("-c", "--crossref", action="store_true", help="Busca títulos formateados desde Crossref")
    fetch.add_argument("-n", "--name", type=str, help="Nombre del registro que se creará")
    fetch.add_argument("--style", choices=["aps", "acs"], default="acs")
    fetch.set_defaults(func=handle_fetch)

    format_choices = ["text", "json", "pdf", "docx", "word", "bib"]

    export = subparsers.add_parser("export")
    export.add_argument("-n", "--name", required=True, type=str, help="Nombre del registro de origen")
    export.add_argument("-f", "--format", required=True, choices=format_choices, help="Formato de salida")
    export.add_argument("-o", "--output", required=True, help="Nombre del archivo de salida")
    export.add_argument("--style", choices=["aps", "acs"], default="acs")
    export.add_argument("--full", action="store_true", help="Incluye papers que han citado los papers")
    export.set_defaults(func=handle_export)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
