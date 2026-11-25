"""Settings in one place, all overridable with environment variables.

Model routing is a cost and quality decision: the strongest general model writes
the product and spec artefacts, Mistral's code model builds, a different model
reviews (so the reviewer is independent of the builder), and specialist models
handle OCR, vision, embeddings and moderation.
"""
import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Models:
    generate: str = _env("MODEL_GENERATE", "mistral-large-latest")
    code: str = _env("MODEL_CODE", "codestral-latest")
    review: str = _env("MODEL_REVIEW", "mistral-medium-latest")
    vision: str = _env("MODEL_VISION", "mistral-medium-latest")
    ocr: str = _env("MODEL_OCR", "mistral-ocr-latest")
    embed: str = _env("MODEL_EMBED", "mistral-embed")
    moderation: str = _env("MODEL_MODERATION", "mistral-moderation-latest")


# Rough USD prices per million tokens, used only for the cost estimate shown
# in the run log. Check https://mistral.ai/pricing and update before relying
# on them; override with PRICE_<MODEL>_IN / _OUT if needed.
DEFAULT_PRICES = {
    "mistral-large-latest": (0.5, 1.5),
    "mistral-medium-latest": (0.4, 2.0),
    "mistral-small-latest": (0.1, 0.3),
    "codestral-latest": (0.3, 0.9),
    "mistral-embed": (0.1, 0.0),
    "mistral-moderation-latest": (0.1, 0.0),
}
OCR_PRICE_PER_PAGE = 0.001


@dataclass(frozen=True)
class Limits:
    max_files: int = 5
    max_file_mb: float = 10.0
    max_context_chars: int = 60_000
    max_idea_chars: int = 5_000
    max_fix_rounds: int = int(_env("MAX_FIX_ROUNDS", "1"))


@dataclass(frozen=True)
class ValueAssumptions:
    """Inputs for the business value estimate. Shown in the UI so a customer can challenge them."""
    pm_hours_per_spec: float = 6.0      # canvas, architecture notes and spec
    dev_hours_per_prototype: float = 8.0  # design, tasks, tests and a clickable prototype
    hourly_rate_gbp: float = 60.0


@dataclass(frozen=True)
class Settings:
    models: Models = field(default_factory=Models)
    limits: Limits = field(default_factory=Limits)
    value: ValueAssumptions = field(default_factory=ValueAssumptions)


SETTINGS = Settings()
