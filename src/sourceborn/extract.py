"""Stdlib-only text extraction for uploaded files (zero dependencies).

Supports the formats the user actually uploads — txt/md/csv/json (plain),
docx/xlsx (Office Open XML = a zip of XML, parsed with zipfile + re), and a
best-effort pdf pass (zlib-inflate the content streams, pull text operators).
No third-party libraries, so it still runs on the zero-build Render deploy.

    text, note = extract_text("table.xlsx", raw_bytes)

``note`` is a human-readable flag for anything the caller should surface
(e.g. a scanned PDF with no extractable text).
"""

from __future__ import annotations

import io
import re
import zlib
import zipfile

PLAIN_EXTS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log",
              ".py", ".js", ".html", ".xml", ".yaml", ".yml"}


def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    """Return (text, note) for an uploaded file. Never raises."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    try:
        if ext in PLAIN_EXTS:
            return data.decode("utf-8", "ignore"), ""
        if ext == ".docx":
            return _docx(data), ""
        if ext == ".xlsx":
            return _xlsx(data), ""
        if ext == ".pdf":
            t = _pdf(data)
            return t, ("" if t.strip() else
                       "PDF had no extractable text (likely scanned or encrypted) "
                       "— paste the text or upload a .docx/.txt instead.")
        return data.decode("utf-8", "ignore"), \
            f"Unknown type '{ext or '?'}' — read as plain text."
    except Exception as exc:                       # never crash an upload
        return "", f"Could not read {filename}: {exc}"


_WT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)
_WP = re.compile(r"</w:p>")


def _docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return _unesc("".join(_WT.findall(_WP.sub("\n", xml)))).strip()


_T = re.compile(r"<t[^>]*>(.*?)</t>", re.S)
_SI = re.compile(r"<si>(.*?)</si>", re.S)
_ROW = re.compile(r"<row[^>]*>(.*?)</row>", re.S)
_CELL = re.compile(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", re.S)
_V = re.compile(r"<v>(.*?)</v>", re.S)


def _xlsx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            sx = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore")
            shared = [_unesc("".join(_T.findall(si))) for si in _SI.findall(sx)]
        sheets = sorted(n for n in names
                        if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        out: list[str] = []
        for sh in sheets:
            sx = z.read(sh).decode("utf-8", "ignore")
            for row in _ROW.findall(sx):
                cells: list[str] = []
                for m in _CELL.finditer(row):
                    attrs, inner = m.group(1) or "", m.group(2) or ""
                    vm = _V.search(inner)
                    if vm is None:
                        inline = _T.findall(inner)
                        if inline:
                            cells.append(_unesc("".join(inline)))
                        continue
                    v = vm.group(1)
                    if 't="s"' in attrs:
                        try:
                            cells.append(shared[int(v)])
                        except (ValueError, IndexError):
                            cells.append(v)
                    else:
                        cells.append(_unesc(v))
                if cells:
                    out.append("\t".join(cells))
    return "\n".join(out).strip()


def _pdf(data: bytes) -> str:
    chunks: list[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except Exception:
            pass
        for tm in re.finditer(rb"\((?:[^()\\]|\\.)*\)", raw):
            chunks.append(tm.group(0)[1:-1].decode("latin-1", "ignore"))
    txt = re.sub(r"\\[()\\]", "", " ".join(chunks))
    return re.sub(r"[ \t]{2,}", " ", txt).strip()


def _unesc(s: str) -> str:
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'"))
