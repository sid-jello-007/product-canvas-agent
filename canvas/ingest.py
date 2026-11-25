"""Turn whatever the user gives us into one written brief.

Ideas arrive in many shapes: a one liner, a Word or PDF brief, an HTML
prototype, or a design exported from Figma as an image. Each type goes to the
right tool (plain parsing, Mistral OCR or a Mistral vision model) and comes
back as labelled text, so every later step works on the same input.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from .llm import LLM

TEXT_TYPES = {".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".js"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
HTML_TYPES = {".html", ".htm"}
SUPPORTED = TEXT_TYPES | set(IMAGE_TYPES) | HTML_TYPES | {".pdf", ".docx"}


@dataclass
class Source:
    name: str
    kind: str
    text: str


@dataclass
class Context:
    sources: list[Source] = field(default_factory=list)
    truncated: bool = False

    def as_prompt(self) -> str:
        # Each source is wrapped in tags so the model treats it as data, not as instructions.
        return "\n\n".join(
            f'<source name="{s.name}" kind="{s.kind}">\n{s.text.strip()}\n</source>' for s in self.sources
        )

    def summary(self) -> str:
        parts = [f"{s.name} ({s.kind}, {len(s.text):,} chars)" for s in self.sources]
        return ", ".join(parts) + (" [truncated to fit the context budget]" if self.truncated else "")


def html_to_text(html: str) -> str:
    """Keep the parts of a prototype that describe the product: headings, copy, buttons, inputs, links."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    lines = []
    if soup.title and soup.title.string:
        lines.append(f"Page title: {soup.title.string.strip()}")
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "button", "a", "label", "input", "select", "textarea"]):
        name = el.name
        if name == "input":
            text = el.get("placeholder") or el.get("name") or el.get("type", "")
            lines.append(f"[input] {text}")
        elif name in {"button", "a"}:
            text = el.get_text(" ", strip=True)
            if text:
                lines.append(f"[{'button' if name == 'button' else 'link'}] {text}")
        else:
            text = el.get_text(" ", strip=True)
            if text:
                prefix = "#" * int(name[1]) + " " if name.startswith("h") else ("- " if name == "li" else "")
                lines.append(f"{prefix}{text}")
    # Drop consecutive duplicates (nested elements repeat text).
    deduped = [line for i, line in enumerate(lines) if i == 0 or line != lines[i - 1]]
    return "\n".join(deduped)


def docx_to_text(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(lines)


def read_file(path: str, llm: LLM) -> Source:
    p = Path(path)
    ext = p.suffix.lower()
    data = p.read_bytes()
    if ext in TEXT_TYPES:
        return Source(p.name, "text", data.decode("utf-8", errors="replace"))
    if ext in HTML_TYPES:
        return Source(p.name, "html prototype", html_to_text(data.decode("utf-8", errors="replace")))
    if ext == ".docx":
        return Source(p.name, "word document", docx_to_text(data))
    if ext == ".pdf":
        return Source(p.name, "pdf (Mistral OCR)", llm.ocr_pdf(p.name, data))
    if ext in IMAGE_TYPES:
        return Source(p.name, "design image (Mistral vision)", llm.describe_image(p.name, data, IMAGE_TYPES[ext]))
    raise ValueError(f"Unsupported file type: {p.name}")


def build_context(idea: str, files: list[str], llm: LLM, max_chars: int) -> Context:
    ctx = Context()
    if idea and idea.strip():
        ctx.sources.append(Source("idea", "brief", idea.strip()))
    for path in files or []:
        ctx.sources.append(read_file(path, llm))

    # Enforce a context budget so cost and latency stay predictable.
    total = 0
    for s in ctx.sources:
        room = max_chars - total
        if len(s.text) > room:
            s.text = s.text[: max(room, 0)]
            ctx.truncated = True
        total += len(s.text)
    ctx.sources = [s for s in ctx.sources if s.text.strip()]
    return ctx
