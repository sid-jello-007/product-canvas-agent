"""Settings in one place, all overridable with environment variables.

Model routing is a cost and quality decision: the strongest model writes the
artefacts, a small fast model judges them, and specialist models handle OCR,
vision, embeddings and moderation.
"""
import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Models:
    generate: str = _env("MODEL_GENERATE", "mistral-large-latest")
    judge: str = _env("MODEL_JUDGE", "mistral-small-latest")
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
    max_refine_rounds: int = int(_env("MAX_REFINE_ROUNDS", "1"))
    pass_score: float = 3.5  # stories scoring below this go back for refinement
    duplicate_threshold: float = 0.92  # cosine similarity that flags near duplicate stories


@dataclass(frozen=True)
class ValueAssumptions:
    """Inputs for the business value estimate. Shown in the UI so a customer can challenge them."""
    pm_hours_per_spec: float = 4.0
    pm_minutes_per_story: float = 20.0
    hourly_rate_gbp: float = 60.0


@dataclass(frozen=True)
class Settings:
    models: Models = field(default_factory=Models)
    limits: Limits = field(default_factory=Limits)
    value: ValueAssumptions = field(default_factory=ValueAssumptions)


SETTINGS = Settings()
