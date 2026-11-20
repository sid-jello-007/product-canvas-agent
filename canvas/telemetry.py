"""Run log: what each step cost, how long it took and which model ran it.

This is the observability layer. In a customer deployment the same events
would go to a dashboard; here they power the 'Run log' tab.
"""
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from .config import DEFAULT_PRICES, OCR_PRICE_PER_PAGE


@dataclass
class Event:
    step: str
    model: str
    seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    pages: int = 0
    status: str = "ok"
    note: str = ""

    @property
    def cost_usd(self) -> float:
        if self.pages:
            return self.pages * OCR_PRICE_PER_PAGE
        price_in, price_out = DEFAULT_PRICES.get(self.model, (0.0, 0.0))
        return (self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000


@dataclass
class Telemetry:
    events: list[Event] = field(default_factory=list)

    @contextmanager
    def track(self, step: str, model: str):
        """Time a step; the caller fills in tokens on the yielded event."""
        event = Event(step=step, model=model, seconds=0.0)
        start = time.perf_counter()
        try:
            yield event
        except Exception as exc:  # record the failure, then let it surface
            event.status = "error"
            event.note = str(exc)[:200]
            raise
        finally:
            event.seconds = round(time.perf_counter() - start, 2)
            self.events.append(event)

    def totals(self) -> dict:
        return {
            "calls": len(self.events),
            "seconds": round(sum(e.seconds for e in self.events), 1),
            "input_tokens": sum(e.input_tokens for e in self.events),
            "output_tokens": sum(e.output_tokens for e in self.events),
            "cost_usd": round(sum(e.cost_usd for e in self.events), 4),
        }

    def rows(self) -> list[list]:
        return [
            [e.step, e.model, e.seconds, e.input_tokens, e.output_tokens, round(e.cost_usd, 5), e.status, e.note]
            for e in self.events
        ]
