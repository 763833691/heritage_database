from __future__ import annotations

import io
from pathlib import Path

KDH_PASSPHRASE = b"FZHMEI"


def decrypt_kdh(raw: bytes) -> bytes:
    origin = raw[254:]
    output = bytearray()
    keycursor = 0
    for origin_byte in origin:
        output.append(origin_byte ^ KDH_PASSPHRASE[keycursor])
        keycursor = (keycursor + 1) % len(KDH_PASSPHRASE)
    data = bytes(output)
    eofpos = data.rfind(b"%%EOF")
    if eofpos < 0:
        raise ValueError("KDH 解密失败：未找到 PDF 结束标记")
    return data[: eofpos + 5]


def extract_pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_bytes(raw: bytes) -> str | None:
    if raw.startswith(b"KDH"):
        return extract_pdf_text(decrypt_kdh(raw)).strip() or None
    if raw.startswith(b"%PDF"):
        return extract_pdf_text(raw).strip() or None
    pdf_idx = raw.find(b"%PDF")
    if pdf_idx >= 0:
        eof_idx = raw.rfind(b"%%EOF")
        if eof_idx > pdf_idx:
            pdf_bytes = raw[pdf_idx : eof_idx + 5]
            text = extract_pdf_text(pdf_bytes).strip()
            if text:
                return text
    return None


def extract_text_from_caj(path: Path) -> str | None:
    raw = path.read_bytes()
    return extract_text_from_bytes(raw)
