"""Sprint 02 文档解析：txt / docx / pdf 文本提取。"""
import io
import re

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+")


def safe_filename(name: str) -> str:
    name = _SAFE_NAME.sub("_", name or "file")
    return name.strip("._") or "file"


def extract_text(filename: str, data: bytes) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".txt") or lower.endswith(".md"):
        return data.decode("utf-8", errors="ignore")
    if lower.endswith(".docx"):
        try:
            from docx import Document

            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise ValueError(f"docx 解析失败: {exc}")
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = []
            for page in reader.pages:
                pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception as exc:
            raise ValueError(f"pdf 解析失败: {exc}")
    raise ValueError("仅支持 txt / docx / pdf 文件")
