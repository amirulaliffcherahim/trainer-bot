"""Knowledge-base ingestion — markdown corpora → kb_chunks.

Pipeline: sources → chunk by heading → local embeddings → kb_chunks.
MarkItDown (free, local) handles non-markdown sources (PDFs, Word, HTML) —
that is its role in this project; screenshots never go through it.

Idempotent: re-ingesting a persona replaces its chunks.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from db import init_db
from retrieval import Embedder, SentenceTransformerEmbedder, TfEmbedder, encode_blob

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$")
_MAX_CHUNK = 1400


@dataclass(frozen=True)
class Chunk:
    title: str
    source: str
    content: str


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """Split markdown into chunks by heading. Tiny chunks merge into the
    previous one; oversized chunks hard-split at newline boundaries.
    """
    chunks: list[Chunk] = []
    current_title = "Introduction"
    current: list[str] = []

    def flush() -> None:
        body = "\n".join(current).strip()
        if body:
            chunks.append(Chunk(title=current_title, source=source, content=body))

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            current_title = match.group(2).strip()
            current = [line]
        else:
            current.append(line)
    flush()

    # Merge tiny chunks into the previous one (heading fragmentation).
    merged: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.content) < 120 and merged:
            previous = merged[-1]
            merged[-1] = Chunk(
                previous.title, previous.source, previous.content + "\n" + chunk.content
            )
        elif len(chunk.content) > _MAX_CHUNK:
            merged.extend(_hard_split(chunk))
        else:
            merged.append(chunk)
    return merged


def _hard_split(chunk: Chunk) -> list[Chunk]:
    parts: list[str] = []
    current = ""
    for para in chunk.content.split("\n\n"):
        if len(current) + len(para) > _MAX_CHUNK and current:
            parts.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        parts.append(current)
    return [Chunk(title=chunk.title, source=chunk.source, content=p) for p in parts]


def _read_source(file: Path) -> str:
    """Markdown/txt pass through; anything else converts via MarkItDown
    (free, local) — that is MarkItDown's role in this project."""
    if file.suffix.lower() in {".md", ".markdown", ".txt"}:
        return file.read_text(encoding="utf-8")
    from markitdown import MarkItDown  # local, no cloud

    return MarkItDown().convert(str(file)).text_content


def ingest_kb(
    conn,
    embedder: Embedder,
    kb_root: Path,
    *,
    clear: bool = True,
) -> int:
    """Ingest every knowledge/<persona>/* into kb_chunks. Returns count."""
    total = 0
    for persona_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        persona = persona_dir.name
        if clear:
            conn.execute("DELETE FROM kb_chunks WHERE persona = ?", (persona,))
        chunks: list[Chunk] = []
        for file in sorted(p for p in persona_dir.iterdir() if p.is_file()):
            chunks.extend(chunk_markdown(_read_source(file), file.name))
        if not chunks:
            continue
        vectors = embedder.embed([c.content for c in chunks])
        conn.executemany(
            "INSERT INTO kb_chunks (persona, title, source, content, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (persona, c.title, c.source, c.content, encode_blob(vectors[i]))
                for i, c in enumerate(chunks)
            ],
        )
        conn.commit()
        total += len(chunks)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge corpora into kb_chunks")
    parser.add_argument("--db", default="trainer_data.db", help="SQLite path")
    parser.add_argument("--kb-root", default="knowledge", help="knowledge base root")
    parser.add_argument(
        "--tf",
        action="store_true",
        help="use the deterministic TfEmbedder instead of sentence-transformers",
    )
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="embedding model name")
    args = parser.parse_args()

    conn = init_db(args.db)
    embedder: Embedder = (
        TfEmbedder() if args.tf else SentenceTransformerEmbedder(args.model)
    )
    count = ingest_kb(conn, embedder, Path(args.kb_root))
    print(f"Ingested {count} chunks into {args.db}")


if __name__ == "__main__":
    main()
