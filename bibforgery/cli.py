#!/usr/bin/python3 -u

# $ bibforgery --fetch 57223337398 --full -o alan_quintal --crossref

from dotenv import load_dotenv
from pathlib import Path
from .tools import fetch_papers_by_author, fetch_citing_articles, get_data_from_file
from .bibtex import dict_to_bibtex, generate_txt, generate_pdf
from .generators import generate_full_json, generate_docx
import argparse, os, json


def dump_json_to_file(data, output="output.json") -> None:
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_name(prefix, name, extension):
    return Path(f"{prefix}/{name}.{extension}")


def main():
    load_dotenv()

    ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY")
    ELSEVIER_INST_TOKEN = os.getenv("ELSEVIER_INSTTOKEN")

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--fetch", metavar="AUTHOR ID", default="", help="Fetch Scopus API with AUTHOR_ID")
    parser.add_argument(
        "--max-entries",
        metavar="",
        type=int,
        default=500,
        help="Límite máximo de artículos recuperados (útil para testing)",
    )
    parser.add_argument("-i", "--input", metavar="BibTex", default="input.txt", help="Nombre de archivo de entrada")
    parser.add_argument("-o", "--output", metavar="JSON, TXT", default="", help="Nombre de archivo de salida")
    parser.add_argument("--parse", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument("--full", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument("--crossref", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument(
        "-f",
        "--format",
        metavar="{text,json,pdf,bib}",
        choices=["text", "json", "pdf", "docx", "word", "bib"],
        default="",
        help="Formato de salida",
    )
    parser.add_argument(
        "--style",
        metavar="{aps,acs}",
        choices=["aps", "acs"],
        default="acs",
    )

    args = parser.parse_args()

    if args.fetch:
        base_data = fetch_papers_by_author(
            args.fetch,
            ELSEVIER_API_KEY,
            ELSEVIER_INST_TOKEN,
            args.max_entries,
            crossref_title=args.crossref,
        )
        base_input_file = resolve_name("output", f"{args.output}_response", "json")
        dump_json_to_file(base_data, base_input_file)
        print(f"Listo: {base_input_file}")

        if args.full:
            print("\nArtículos citados:")

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
                    citedby_json_filename = resolve_name(
                        f"output/{args.output}", f"{args.output}_{eid}_citedby", "json"
                    )
                    dump_json_to_file(cites_data, citedby_json_filename)
                    print(f"   Listo: {citedby_json_filename}\n")
        return

    if not args.parse or not args.format:
        parser.error("Debes especificar el tipo de uso: --fetch ó --parse")

    if args.format == "bib":
        input_file = resolve_name("output", f"{args.input}_response", "json")
        raw_data = get_data_from_file(input_file)
        json_data = json.loads(raw_data)
        bibtex_data = dict_to_bibtex(json_data)

        output_file = resolve_name("output", f"{args.input}", "bib")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(bibtex_data)

        print("[Info] — BibTex created")

    elif args.format == "json":
        json_data = generate_full_json(args.input, include_citations=args.full)
        output_path = resolve_name("output", args.output, "json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print("[Info] — JSON created")

    elif args.format == "text":
        input_file = resolve_name("output", f"{args.input}", "bib")
        raw_data = get_data_from_file(input_file)
        text_as_bytes = generate_txt(raw_data)
        output_file = resolve_name("output", f"{args.output or 'text'}", "txt")
        with open(output_file, "wb") as file:
            file.write(text_as_bytes.getvalue())
        print("[Info] — Text file created")

    elif args.format == "pdf":
        input_file = resolve_name("output", f"{args.input}", "bib")
        raw_data = get_data_from_file(input_file)
        pdf_as_bytes = generate_pdf(raw_data)
        output_file = resolve_name("output", f"{args.output or 'cites'}", "pdf")
        with open(output_file, "wb") as f:
            f.write(pdf_as_bytes)
        print("[Info] — PDF created")

    elif args.format == "docx" or args.format == "word":
        generate_docx(
            args.input,
            output=resolve_name("output", args.output, "docx"),
            include_citations=args.full,
            citation_style=1 if args.style.lower() == "acs" else 2,
        )
