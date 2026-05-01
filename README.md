!["BibForgery — BibTeX → { txt | json | pdf }"](https://raw.githubusercontent.com/Edescal/BibForgery/main/assets/bibforgery.png)

# BibForgery v1.0
## Script para obtener artículos de Scopus y convertirlos a distintos formatos.

**Autor:** Eduardo Escalante Pacheco  
**Fecha:** 17 de abril de 2026

### Uso:
```bash
    python3 bibforgery.py [--fetch AUTHOR_ID] [--to-bibtex] [-f {text,json}] [-i INPUT] [-o OUTPUT]

    python3 bibforgery.py [-f {text,json,pdf}] [-i INPUT] [-o OUTPUT]
```
### Opciones:
```bash
    --fetch AUTHOR_ID   (opcional) Obtiene artículos del autor desde Scopus
    --to-bibtex         (opcional) Transforma la respuesta a formato BibTex
    --parse             (opcional) Indica que se va a parsear un archivo BibTex
    -f, --format        (opcional) Formato de salida: text o json
    -i, --input         (opcional) Archivo de entrada (default: input.txt)
    -o, --output        (opcional) Archivo de salida (default: output.txt)
```
### Ejemplos:
```bash
    python3 bibforgery.py --fetch 56000743500
    python3 bibforgery.py -f json -i data.txt -o out.json
    python3 bibforgery.py -f pdf -i input.bib -o output.pdf
```