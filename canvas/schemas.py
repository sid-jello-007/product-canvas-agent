"""Data contracts for every artefact in the flow.

Each agent must return JSON matching one of these models. Mistral's structured
outputs enforce the shape while the model writes, and Pydantic checks it again,
so the validator, renderers and UI can rely on the data instead of parsing prose.

Every field is required on purpose: strict JSON schema mode works best when the
model cannot skip fields.
"""
from typing import Literal

from pydantic import BaseModel, Field


# ======================= 01 Domain store =======================

# ---------- Product canvas (PO inputs -> epics -> features -> proposal) ----------

class Feature(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(description="Testable statements of done")
    test_scenarios: list[str] = Field(description="Short 'when ..., then ...' examples")


class CanvasEpic(BaseModel):
    title: str
    outcome: str = Field(description="The user or business outcome this epic delivers")
    features: list[Feature]


class Metric(BaseModel):
    name: str
    target: str


class ProductCanvas(BaseModel):
    product_name: str
    change_id: str = Field(description="kebab-case id for this change, e.g. add-savings-pots")
    problem: str
    target_users: list[str]
    value_proposition: str
    epics: list[CanvasEpic]
    success_metrics: list[Metric]
    out_of_scope: list[str]
    assumptions: list[str]
    clarifying_questions: list[str] = Field(description="Questions for the product owner; empty if none")


# ---------- Architecture (intent, patterns, CALM style model, decisions, NFRs) ----------

class Node(BaseModel):
    unique_id: str = Field(description="kebab-case id")
    node_type: Literal["actor", "webclient", "service", "database", "system", "data-asset"]
    name: str
    description: str


class Relationship(BaseModel):
    unique_id: str
    source: str = Field(description="unique_id of the source node")
    destination: str = Field(description="unique_id of the destination node")
    protocol: str = Field(description="e.g. HTTPS, browser storage, none")
    description: str


class Decision(BaseModel):
    title: str
    decision: str
    rationale: str


class NFR(BaseModel):
    id: str = Field(description="NFR-1, NFR-2, ...")
    category: Literal["performance", "security", "privacy", "accessibility", "reliability", "usability", "compliance"]
    statement: str = Field(description="Measurable statement using SHALL")


class Interface(BaseModel):
    name: str
    kind: Literal["ui", "api", "event", "storage"]
    description: str


class Architecture(BaseModel):
    intent: str
    patterns: list[str]
    nodes: list[Node]
    relationships: list[Relationship]
    decisions: list[Decision]
    nfrs: list[NFR]
    controls: list[str]
    interfaces: list[Interface]


# ---------- Shared spec (OpenSpec change: proposal + capability specs) ----------

class Scenario(BaseModel):
    name: str
    given: str = Field(description="Starting state; empty string if not needed")
    when: str
    then: str


class SpecRequirement(BaseModel):
    name: str = Field(description="Short requirement name, used as the '### Requirement:' heading")
    statement: str = Field(description="Normative statement containing SHALL or MUST")
    kind: Literal["functional", "non-functional"]
    traces_to: list[str] = Field(description="Canvas feature titles or NFR ids this requirement comes from")
    scenarios: list[Scenario]


class Capability(BaseModel):
    name: str = Field(description="kebab-case capability name, e.g. pot-management")
    purpose: str
    requirements: list[SpecRequirement]


class Proposal(BaseModel):
    why: str
    what_changes: list[str]
    impact: str


class Conflict(BaseModel):
    between: str = Field(description="Which inputs conflict, e.g. 'Canvas feature X vs NFR-2'")
    description: str
    question: str = Field(description="The question that would resolve it")


class SpecPackage(BaseModel):
    proposal: Proposal
    capabilities: list[Capability]
    conflicts: list[Conflict] = Field(description="Requirement or architecture conflicts; empty if none")


# ======================= 02 Delivery to the target =======================

class Exploration(BaseModel):
    target_summary: str = Field(description="What exists today in the target, or 'greenfield'")
    baseline_findings: list[str]
    implementation_delta: list[str] = Field(description="What must change in the target to meet the spec")
    risks: list[str]


class DesignDoc(BaseModel):
    context: str
    goals: list[str]
    non_goals: list[str]
    decisions: list[Decision]
    ui_structure: list[str] = Field(description="Screens or sections and the data-testid of key elements")
    state_and_data: str
    test_strategy: str
    risks_and_tradeoffs: list[str]


class Task(BaseModel):
    id: str = Field(description="Like 1.1, 1.2, 2.1")
    description: str
    requirements: list[str] = Field(description="Requirement names this task implements")


class TaskGroup(BaseModel):
    number: int
    title: str
    tasks: list[Task]


class ScenarioTest(BaseModel):
    scenario: str = Field(description="Scenario name from the spec")
    test_name: str
    steps: list[str] = Field(description="Plain steps referencing data-testid values")


class TaskPlan(BaseModel):
    groups: list[TaskGroup]
    qa_plan: list[ScenarioTest]


class QAResult(BaseModel):
    scenario: str
    status: Literal["pass", "fail"]
    evidence: str = Field(description="Where in the code the behaviour is implemented, or what is missing")
    owner: Literal["app", "test", "spec", "none"] = Field(description="Who should fix a failure; 'none' if it passed")


class QAReview(BaseModel):
    results: list[QAResult]
    summary: str
