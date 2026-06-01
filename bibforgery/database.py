import sqlite3


def init_db():
    conn = sqlite3.connect("papers.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
        eid TEXT PRIMARY KEY,
        title TEXT,
        year INTEGER,
        author_id INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_citations (
        paper_eid TEXT,
        cited_eid TEXT,
        PRIMARY KEY (paper_eid, cited_eid)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            scopus_id TEXT PRIMARY KEY,
            name TEXT
        )               
    """)
    conn.commit()


def get_connection():
    conn = sqlite3.connect("papers.db")
    conn.row_factory = sqlite3.Row
    return conn


def read_papers(author_id:str, full:bool):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM authors
        JOIN papers ON
        authors.scopus_id = papers.author_id
        """)
        for row in cursor.fetchall():
            print(f'Name: {row['']}')
    