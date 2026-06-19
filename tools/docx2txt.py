"""Tiny .docx -> text helper (stdlib only) so you can feed Word files to the brain.

    python tools/docx2txt.py "My Core.docx" > "My Core.txt"

A .docx is just a zip; we read word/document.xml and strip the tags. Good enough
to turn your cores/raw-thoughts into ingestible plain text. For .pdf/.xlsx, export
to .txt/.csv from the source app.
"""

from __future__ import annotations

import re
import sys
import zipfile


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = xml.replace("</w:p>", "\n")
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python tools/docx2txt.py <file.docx>", file=sys.stderr)
        raise SystemExit(2)
    print(docx_text(sys.argv[1]))
