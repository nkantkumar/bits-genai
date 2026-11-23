"""Ingestion: load raw newsroom files into clean Documents with metadata.

This is stage 1 of the RAG pipeline. Real archives are messy (HTML, mixed
formats, boilerplate), so ingestion's job is: get clean text out, and capture
the metadata (source, date, author, section) we will need later for citations,
access control, and freshness.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup


@dataclass
class Document:
    """A single ingested document: clean text plus where it came from."""
    text: str
    metadata: dict = field(default_factory=dict)


def _parse_frontmatter(raw):
    """Split a leading '--- ... ---' metadata block from the body text."""
    if not raw.startswith("---"):
        return {}, raw.strip()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw.strip()
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].strip()


def load_markdown(path):
    """Load a .md/.txt article: metadata from frontmatter, body as clean text."""
    raw = Path(path).read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    meta.setdefault("source", Path(path).name)
    return Document(text=body, metadata=meta)


def load_html(path):
    """Load a messy HTML page: strip nav/ads/boilerplate, keep the article text."""
    soup = BeautifulSoup(Path(path).read_text(encoding="utf-8"), "html.parser")
    for tag in soup(["nav", "header", "footer", "aside", "script", "style"]):
        tag.decompose()
    body = soup.find("article") or soup.body or soup
    text = body.get_text(separator="\n")
    clean = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    meta = {
        "source": Path(path).name,
        "title": soup.title.get_text(strip=True) if soup.title else Path(path).stem,
        "section": "Wire",
        "publication": "MetroWire",
    }
    return Document(text=clean, metadata=meta)


LOADERS = {".md": load_markdown, ".txt": load_markdown, ".html": load_html}


def ingest_folder(folder):
    """Walk a folder, send each file to the loader for its type, return Documents."""
    docs = []
    for path in sorted(Path(folder).rglob("*")):
        loader = LOADERS.get(path.suffix.lower())
        if loader is None:
            continue
        docs.append(loader(path))
    return docs
