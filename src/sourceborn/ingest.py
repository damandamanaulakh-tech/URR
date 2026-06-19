"""Feed the brain — ingest the user's corpus so muscle memory compounds.

"It will keep adding my example and my way of answering." This walks a folder of
text/markdown files (your 314 cores, raw thoughts, chats) and writes each into
the memory store + (optionally) the persona example bank. Run it any time you
have new material; the brain grows without retraining anything.

Binary formats (.docx/.pdf/.xlsx) are skipped here — convert them to .txt/.md
first (the repo has a tiny docx->txt helper in tools/). Keeping ingestion to
plain text keeps the brain transparent and ownable.
"""

from __future__ import annotations

import os
from typing import Iterable

from .enums import Classification, EvidenceTag
from .memory import Memory
from .models import MemoryEntry, RawSource
from .persona import Persona

TEXT_EXTS = {".txt", ".md", ".markdown"}


def iter_text_files(folder: str) -> Iterable[str]:
    for dirpath, _dirs, files in os.walk(folder):
        for fn in files:
            if os.path.splitext(fn)[1].lower() in TEXT_EXTS:
                yield os.path.join(dirpath, fn)


def ingest_folder(
    folder: str,
    root: str = ".sourceborn",
    node_id: str = "SB-07",
    learn_voice: bool = True,
    max_chars: int = 20000,
) -> dict[str, int]:
    """Ingest every text file under ``folder`` into the brain.

    Returns counts of files ingested and memory entries written.
    """
    memory = Memory(root)
    persona = Persona(root) if learn_voice else None
    files = 0
    entries = 0
    for path in iter_text_files(folder):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()[:max_chars]
        except Exception:
            continue
        if not text.strip():
            continue
        raw = RawSource(text=text, origin=f"corpus:{os.path.basename(path)}").lock()
        memory.write(node_id, MemoryEntry(
            node_id=node_id, raw_source_id=raw.raw_source_id,
            content=text[:4000],
            classification=Classification.REVIEW_ONLY.value,
            evidence_tag=EvidenceTag.REVIEW.value,
            tags=["corpus", os.path.basename(path)],
            parameters={"source_path": path, "chars": len(text)},
        ), name="First Memory Write")
        entries += 1
        files += 1
        if persona is not None:
            # treat the file as one of the user's "way of answering" examples
            persona.learn(
                question=os.path.basename(path),
                answer=text[:1200],
                note="ingested corpus file",
            )
    memory.master_log({"event": "ingest", "folder": folder,
                       "files": files, "entries": entries})
    return {"files": files, "entries": entries, **memory.stats()}
