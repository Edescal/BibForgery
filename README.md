!["BibForgery — Scopus → { bib | json | pdf | docx | txt }"](https://raw.githubusercontent.com/Edescal/BibForgery/main/assets/bibforgery.png)

# BibForgery v1.10

A command-line tool for retrieving publications from Scopus, storing them locally, and exporting them to multiple formats.

---

## Installation

```bash
pip install bibforgery
```


## Usage

```bash
bibforgery <command> [options]
```

## Commands

### fetch

Retrieve publications from a Scopus author profile and store them locally.

```bash
bibforgery fetch SCOPUS_ID [options]
```

#### Arguments

```text
SCOPUS_ID              Scopus Author ID
```

#### Options

```text
-f, --full             Include citing publications
-c, --crossref         Normalize titles using Crossref
-n, --name NAME        Name of the local record
```

#### Examples

```bash
bibforgery fetch 56000743500

bibforgery fetch 56000743500 \
    --crossref \
    --name theochem

bibforgery fetch 56000743500 \
    --full
```


### export

Export a previously stored record to a supported format.

```bash
bibforgery export NAME -f FORMAT -o OUTPUT [options]
```

#### Supported Formats

```text
text
json
bib
pdf
docx
word
```

#### Options

```text
-f, --format FORMAT    Output format
-o, --output FILE      Output file path

--style {acs,aps}      Citation style
--full                 Include citing publications
```

#### Examples

```bash
bibforgery export theochem \
    -f json \
    -o papers.json

bibforgery export theochem \
    -f pdf \
    -o report.pdf

bibforgery export theochem \
    -f docx \
    -o report.docx \
    --style aps
```


### db

Database and cache management commands.

```bash
bibforgery db <action> [options]
```

#### Available Actions

##### List stored records

```bash
bibforgery db list
```

##### Display cache information

```bash
bibforgery db cacheinfo
```

##### Repair cache entries

```bash
bibforgery db cachefix [options]
```

Options:

```text
-l, --limit N          Maximum number of entries to process
--dry-run              Simulate changes without saving
```

Examples:

```bash
bibforgery db cachefix

bibforgery db cachefix \
    --limit 100

bibforgery db cachefix \
    --dry-run
```

##### Rebuild cached data

```bash
bibforgery db recache -n NAME [options]
```

Options:

```text
-n, --name NAME        Source record name
--full                 Include citing publications
```

Examples:

```bash
bibforgery db recache \
    --name theochem

bibforgery db recache \
    --name theochem \
    --full
```