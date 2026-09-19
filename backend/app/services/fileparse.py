"""合同/项目文件解析：PDF（按页抽文本）、Word、图片、纯文本。"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path

TEXT_EXTS = {".txt", ".md", ".csv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

MAX_TEXT_CHARS = 60000  # 发给 AI 的正文上限


def sniff_kind(filename: str, mime: str | None) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or (mime and "pdf" in mime):
        return "pdf"
    if ext == ".docx" or (mime and "wordprocessingml" in mime):
        return "docx"
    if ext == ".doc":
        return "doc_legacy"
    if ext in IMAGE_EXTS or (mime and mime.startswith("image/")):
        return "image"
    if ext in TEXT_EXTS or (mime and mime.startswith("text/")):
        return "text"
    return "unknown"


def parse_file(path: str | Path, filename: str, mime: str | None = None) -> dict:
    """解析文件 → {"kind", "pages":[{"page":1,"text":"..."}], "images":[b64...], "truncated":bool, "error":None}

    PDF 扫描件（整页无文本）会把该页渲染成图片交给视觉模型 OCR。
    """
    kind = sniff_kind(filename, mime)
    path = Path(path)
    result = {"kind": kind, "pages": [], "images": [], "truncated": False, "error": None}
    try:
        if kind == "pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            for i, page in enumerate(doc, start=1):
                text = (page.get_text("text") or "").strip()
                if text:
                    result["pages"].append({"page": i, "text": text})
                else:
                    # 扫描页 → 渲染为图片待视觉 OCR
                    pix = page.get_pixmap(dpi=120)
                    result["images"].append({
                        "page": i,
                        "b64": base64.b64encode(pix.tobytes("png")).decode(),
                    })
                if i >= 40:
                    result["truncated"] = True
                    break
            doc.close()
        elif kind == "docx":
            import docx
            d = docx.Document(str(path))
            buf = []
            for para in d.paragraphs:
                if para.text.strip():
                    buf.append(para.text.strip())
            for t in d.tables:
                for row in t.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        buf.append(" | ".join(cells))
            result["pages"].append({"page": None, "text": "\n".join(buf)})
        elif kind == "doc_legacy":
            result["error"] = "暂不支持旧版 .doc 格式，请另存为 .docx 或 PDF 后上传。"
        elif kind == "image":
            data = path.read_bytes()
            result["images"].append({"page": 1, "b64": base64.b64encode(data).decode()})
        elif kind == "text":
            raw = path.read_bytes()
            for enc in ("utf-8", "gbk", "utf-16"):
                try:
                    text = raw.decode(enc)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    text = None
            if text is None:
                text = raw.decode("utf-8", errors="replace")
            result["pages"].append({"page": None, "text": text})
        else:
            result["error"] = "不支持的文件类型，请上传 PDF / Word(.docx) / 图片 / 文本文件。"
    except binascii.Error:
        result["error"] = "文件损坏或格式不正确。"
    except Exception as e:  # noqa: BLE001
        result["error"] = f"文件解析失败：{e}"
    return result


def build_llm_text(parsed: dict) -> str:
    """把解析结果拼成发给 AI 的纯文本（带页码标记）。"""
    parts = []
    for p in parsed.get("pages", []):
        tag = f"[第{p['page']}页]" if p.get("page") else ""
        parts.append(f"{tag}\n{p['text']}")
    text = "\n\n".join(parts).strip()
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
        parsed["truncated"] = True
    return text
