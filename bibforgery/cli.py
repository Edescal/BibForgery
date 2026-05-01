from dotenv import load_dotenv
from pathlib import Path
from .tools import (
    fetch_papers,
    data_to_bibtex,
    get_data_from_file,
)
from .generators import (
    generate_json,
    generate_pdf,
    generate_txt,
)
import argparse, os, json


def dump_json_to_file(data, output="output.json") -> None:
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nListo: {output}")


def dump_data_to_bib_file(data: str, output_file="output.bib") -> None:
    output_path = Path(output_file).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(data)
    print(f"Listo: {output_file}")


def main():
    load_dotenv()

    elsevier_api_key = os.getenv("ELSEVIER_API_KEY")
    elsevier_inst_token = os.getenv("ELSEVIER_INSTTOKEN")

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
    parser.add_argument("-o", "--output", metavar="JSON, TXT", default="", help="Nombre de aArchivo de salida")
    parser.add_argument("--parse", action="store_true", help="Parse JSON to Bibtex")
    parser.add_argument(
        "-f",
        "--format",
        metavar="{text,json,pdf}",
        choices=["text", "json", "pdf"],
        default="",
        help="Formato de salida",
    )

    args = parser.parse_args()

    if args.fetch:
        data = fetch_papers(args.fetch, elsevier_api_key, elsevier_inst_token, args.max_entries)

        output_path_base = Path(f"output/{args.output}" if args.output else "output/result.txt")
        output_path = output_path_base.with_name(output_path_base.stem + "_raw.json")
        dump_json_to_file(data, output_path)

        bib_data = data_to_bibtex(data)
        bib_output_file = output_path_base.with_name(output_path_base.stem + ".bib")
        dump_data_to_bib_file(bib_data, bib_output_file)
        return

    if not args.parse or not args.format:
        parser.error("Debes especificar el tipo de uso: --fetch ó --parse")

    if args.format == "json":
        output_path = Path(f"output/{args.output}" if args.output else "output/parse_result")
        o_f_ext = output_path.with_name(output_path.stem + ".json")
        data = get_data_from_file(args.input)
        json_as_bytes = generate_json(data)

        output_path = Path(o_f_ext).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(json_as_bytes.getvalue())

        print("[Info] — JSON created")

    elif args.format == "text":
        output_path = Path(f"output/{args.output}" if args.output else "output/parse_result")
        o_f_ext = output_path.with_name(output_path.stem + ".txt")
        data = get_data_from_file(args.input)
        text_as_bytes = generate_txt(data)

        output_path = Path(o_f_ext).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as file:
            file.write(text_as_bytes.getvalue())

        print("[Info] — Data created")

    elif args.format == "pdf":
        output_path = Path(f"output/{args.output}" if args.output else "output/parse_result")
        o_f_ext = output_path.with_name(output_path.stem + ".pdf")
        data = get_data_from_file(args.input)
        pdf_as_bytes = generate_pdf(data)

        output_path = Path(o_f_ext).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_as_bytes)

        print("[Info] — PDF created")
