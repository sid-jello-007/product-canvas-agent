"""Data contracts for every step of the workflow.

Each agent must return JSON that matches one of these models. Mistral's
structured outputs feature enforces the shape at generation time, and Pydantic
validates it again on our side, so downstream steps (evals, exports, the UI)
can rely on the data instead of parsing free text.

Every field is required on purpose: Mistral's strict JSON schema mode works
best when the model cannot skip fields.
"""
from typing import Literal

from pydantic import BaseModel, Field


# ---------- Step 1: product canvas ----------

class Persona(BaseModel):
    name: str = Field(description="Short persona label, e.g. 'Busy flat sharer'")
    needs: str = Field(description="What this persona needs, in one sentence")


class SuccessMetric(BaseModel):
    name: str = Field(description="Metric name, e.g. 'Weekly active groups'")
    target: str = Field(description="Target value and timeframe, e.g. '1,000 within 3 months'")
    why: str = Field(description="Why this metric shows the product is working")


class ProductCanvas(BaseModel):
    product_name: str
    one_line_pitch: str
    problem: str
    target_users: list[Persona]
    jobs_to_be_done: list[str]
    value_proposition: str
    key_features: list[str]
    success_metrics: list[SuccessMetric]
    assumptions_and_risks: list[str]
    out_of_scope: list[str]
    open_questions: list[str]


# ---------- Step 2: product spec ----------

Priority = Literal["Must", "Should", "Could"]


class Requirement(BaseModel):
    id: str = Field(description="Stable id like FR-1, FR-2")
    title: str
    description: str
    priority: Priority


class ProductSpec(BaseModel):
    overview: str
    goals: list[str]
    non_goals: list[str]
    requirements: list[Requirement]
    non_functional_requirements: list[str]
    user_flows: list[str]


# ---------- Step 3: tickets ----------

JiraPriority = Literal["Highest", "High", "Medium", "Low"]


class Story(BaseModel):
    key: str = Field(description="Story key like E1-S1")
    title: str
    user_story: str = Field(description="'As a <user>, I want <goal>, so that <benefit>.'")
    acceptance_criteria: list[str] = Field(description="Each item in 'Given ..., when ..., then ...' form")
    story_points: int = Field(description="Fibonacci estimate: 1, 2, 3, 5, 8 or 13")
    priority: JiraPriority
    requirement_ids: list[str] = Field(description="Spec requirement ids this story delivers, e.g. ['FR-1']")
    labels: list[str]
    dependencies: list[str] = Field(description="Keys of stories that must ship first")


class Epic(BaseModel):
    key: str = Field(description="Epic key like E1")
    title: str
    summary: str
    stories: list[Story]


class TicketPlan(BaseModel):
    epics: list[Epic]

    def all_stories(self) -> list[Story]:
        return [s for e in self.epics for s in e.stories]


# ---------- Step 4: critic (LLM as judge) ----------

class StoryReview(BaseModel):
    key: str
    score: int = Field(description="1 to 5 against the INVEST criteria, 5 is best")
    issues: list[str] = Field(description="Concrete problems; empty if none")


class Critique(BaseModel):
    reviews: list[StoryReview]
    overall_comment: str


class RefinedStories(BaseModel):
    stories: list[Story]
