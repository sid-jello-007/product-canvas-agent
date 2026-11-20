"""The only place that talks to Mistral.

Keeping every model call behind one small interface gives us three things:
retries and rate limit handling in one spot, telemetry on every call, and a
drop-in fake for tests and demo mode, so the rest of the code never knows
whether a real model answered.
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .config import SETTINGS
from .telemetry import Telemetry

T = TypeVar("T", bound=BaseModel)
RETRYABLE = {429, 500, 502, 503, 504}


class LLM(Protocol):
    telemetry: Telemetry

    def structured(self, step: str, model: str, system: str, user: str, schema: Type[T]) -> T: ...
    def describe_image(self, name: str, data: bytes, mime: str) -> str: ...
    def ocr_pdf(self, name: str, data: bytes) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def moderate(self, text: str) -> list[str]: ...


def _status(exc: Exception) -> int | None:
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "raw_response", None), "status_code", None)
    return code


class MistralLLM:
    """Real implementation on the official mistralai SDK."""

    def __init__(self, api_key: str | None = None, telemetry: Telemetry | None = None):
        from mistralai.client import Mistral
        from mistralai.extra.utils.response_format import response_format_from_pydantic_model

        key = api_key or os.getenv("MISTRAL_API_KEY")
        if not key:
            raise RuntimeError("MISTRAL_API_KEY is not set")
        self.client = Mistral(api_key=key)
        self._schema_format = response_format_from_pydantic_model
        self.telemetry = telemetry or Telemetry()

    # --- plumbing ---

    def _with_retries(self, fn, attempts: int = 4):
        """Back off and retry on rate limits and server errors (the free tier is rate limited)."""
        for i in range(attempts):
            try:
                return fn()
            except Exception as exc:
                if _status(exc) not in RETRYABLE or i == attempts - 1:
                    raise
                time.sleep(2 ** i)

    @staticmethod
    def _usage(event, response):
        usage = getattr(response, "usage", None)
        if usage:
            event.input_tokens = usage.prompt_tokens or 0
            event.output_tokens = usage.completion_tokens or 0

    # --- capabilities ---

    def structured(self, step: str, model: str, system: str, user: str, schema: Type[T]) -> T:
        """Ask for JSON that must match `schema`. One repair attempt if validation still fails."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for attempt in range(2):
            with self.telemetry.track(step if attempt == 0 else f"{step} (repair)", model) as ev:
                resp = self._with_retries(lambda: self.client.chat.complete(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    response_format=self._schema_format(schema),
                ))
                self._usage(ev, resp)
                content = resp.choices[0].message.content
                try:
                    return schema.model_validate_json(content)
                except ValidationError as err:
                    ev.status = "invalid"
                    ev.note = str(err)[:200]
                    messages += [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": f"That JSON failed validation: {err}. Return corrected JSON only."},
                    ]
        raise RuntimeError(f"{step}: model output did not match the schema after a repair attempt")

    def describe_image(self, name: str, data: bytes, mime: str) -> str:
        """Turn a design (Figma export, screenshot, sketch) into a written description of screens and flows."""
        url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        prompt = (
            "This is a product design. Describe every screen you can see: its purpose, the main UI elements, "
            "the actions a user can take and any visible copy or data. Then infer the user flow. "
            "Be factual; say 'unclear' rather than guess."
        )
        model = SETTINGS.models.vision
        with self.telemetry.track(f"vision: {name}", model) as ev:
            resp = self._with_retries(lambda: self.client.chat.complete(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": url},
                ]}],
                temperature=0.1,
            ))
            self._usage(ev, resp)
            return resp.choices[0].message.content

    def ocr_pdf(self, name: str, data: bytes) -> str:
        """Mistral OCR keeps headings and tables as markdown, which matters for specs and briefs."""
        url = f"data:application/pdf;base64,{base64.b64encode(data).decode()}"
        model = SETTINGS.models.ocr
        with self.telemetry.track(f"ocr: {name}", model) as ev:
            resp = self._with_retries(lambda: self.client.ocr.process(
                model=model,
                document={"type": "document_url", "document_url": url},
            ))
            ev.pages = len(resp.pages)
            return "\n\n".join(p.markdown for p in resp.pages)

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = SETTINGS.models.embed
        with self.telemetry.track("embeddings: duplicate check", model) as ev:
            resp = self._with_retries(lambda: self.client.embeddings.create(model=model, inputs=texts))
            ev.input_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
            return [d.embedding for d in resp.data]

    def moderate(self, text: str) -> list[str]:
        """Return the moderation categories that were flagged (empty list means safe)."""
        model = SETTINGS.models.moderation
        with self.telemetry.track("guardrail: moderation", model) as ev:
            resp = self._with_retries(lambda: self.client.classifiers.moderate(model=model, inputs=[text[:20_000]]))
            self._usage(ev, resp)
            categories = resp.results[0].categories or {}
            return [name for name, flagged in categories.items() if flagged]


class FakeLLM:
    """Deterministic stand in used by tests and by demo mode when no API key is configured."""

    def __init__(self, telemetry: Telemetry | None = None):
        from . import demo

        self.demo = demo
        self.telemetry = telemetry or Telemetry()

    def structured(self, step, model, system, user, schema):
        with self.telemetry.track(step, f"demo ({model})") as ev:
            ev.input_tokens, ev.output_tokens = len(user) // 4, 400
            return self.demo.respond(schema, user)

    def describe_image(self, name, data, mime):
        with self.telemetry.track(f"vision: {name}", "demo"):
            return f"[demo] Design '{name}': a home screen listing shared bills and an 'Add bill' button."

    def ocr_pdf(self, name, data):
        with self.telemetry.track(f"ocr: {name}", "demo") as ev:
            ev.pages = 1
            return f"[demo] Text extracted from {name}."

    def embed(self, texts):
        with self.telemetry.track("embeddings: duplicate check", "demo"):
            # Bag of words vectors: good enough to exercise the duplicate logic offline.
            vocab = sorted({w for t in texts for w in t.lower().split()})
            index = {w: i for i, w in enumerate(vocab)}
            vectors = []
            for t in texts:
                v = [0.0] * len(vocab)
                for w in t.lower().split():
                    v[index[w]] += 1.0
                vectors.append(v)
            return vectors

    def moderate(self, text):
        with self.telemetry.track("guardrail: moderation", "demo"):
            return []


def make_llm(telemetry: Telemetry | None = None) -> tuple[LLM, bool]:
    """Real Mistral if a key is configured, otherwise demo mode. Returns (llm, is_demo)."""
    if os.getenv("MISTRAL_API_KEY"):
        return MistralLLM(telemetry=telemetry), False
    return FakeLLM(telemetry=telemetry), True


def to_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(), indent=2, ensure_ascii=False)
