from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.utils.get_tender import TenderResponse


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str | None

    class Config:
        from_attributes = True


# ChileCompra schemas
class Party(BaseModel):
    mp_id: str
    rut: str
    roles: list[str]
    date: datetime | None = None
    amount: float | None = None
    currency: str | None = None


class Tender(BaseModel):
    ocid: str
    title: str
    publishedDate: datetime
    parties: list[Party]


# LangGraph Workflow schemas
class RankingInput(BaseModel):
    """Input for the ranking agent - tender context"""
    tender_id: str = Field(description="Tender/procurement ID")
    tender_name: str = Field(description="Name of the tender")
    tender_date: str = Field(description="Date of the tender")
    bases: str = Field(description="General tender specifications")
    bases_tecnicas: str = Field(description="Technical specifications")
    additional_context: Dict[str, Any] = Field(default_factory=dict, description="Additional context data")


class RankedItem(BaseModel):
    """A single ranked item with risk assessment"""
    tender_id: str = Field(description="Tender/procurement ID")
    risk_score: float = Field(description="Risk score from 0 to 1")
    risk_indicators: List[str] = Field(description="List of identified risk indicators")
    full_context: Dict[str, Any] = Field(description="Complete tender context for investigation")
    ranking_reason: str = Field(description="Explanation of why this was ranked at this position")


class RankingOutput(BaseModel):
    """Output from the ranking agent"""
    ranked_items: List[RankedItem] = Field(description="Top 5 ranked items by risk")
    analysis_summary: str = Field(description="Overall analysis summary")


class FraudDetectionInput(BaseModel):
    """Input for fraud detection agent - single tender to investigate"""
    tender_id: str = Field(description="Tender ID to investigate")
    risk_indicators: List[str] = Field(description="Risk indicators from ranking")
    full_context: Dict[str, Any] = Field(description="Complete context from ranking agent")


class Anomaly(BaseModel):
    """A detected anomaly or fraud indicator"""
    anomaly_name: str = Field(description="Name/type of the anomaly")
    description: str = Field(description="Detailed description of the anomaly")
    evidence: List[str] = Field(description="Supporting evidence from investigation")
    confidence: float = Field(description="Confidence score from 0 to 1")
    affected_documents: List[str] = Field(default_factory=list, description="Documents where anomaly was found")


class FraudDetectionOutput(BaseModel):
    """Output from fraud detection agent"""
    tender_id: str = Field(description="Investigated tender ID")
    is_fraudulent: bool = Field(description="Whether fraud indicators were found")
    anomalies: List[Anomaly] = Field(description="List of detected anomalies")
    investigation_summary: str = Field(description="Summary of the investigation")


class WorkflowState(BaseModel):
    """State management for LangGraph workflow"""
    # Input
    tender_id: str | None = None

    # Fetched tender data
    tender_response: Any = None  # TenderResponse from get_tender()
    tender_documents: List[Dict[str, Any]] = Field(default_factory=list)

    # Processed input for ranking
    input_data: RankingInput | None = None

    # Ranking results
    ranked_items: List[RankedItem] = Field(default_factory=list)

    # Investigation results
    investigation_results: List[FraudDetectionOutput] = Field(default_factory=list)
    final_fraud_cases: List[FraudDetectionOutput] = Field(default_factory=list)

    # Error tracking
    errors: List[str] = Field(default_factory=list)


# Task-based Investigation schemas
class RankedTask(BaseModel):
    """A single investigation task with all required fields"""
    id: int = Field(description="Task ID number")
    code: str = Field(description="Task code (e.g., H-01, H-02)")
    name: str = Field(description="Task name/title")
    desc: str = Field(description="Detailed description of what to validate")
    where_to_look: str = Field(description="Where to find relevant information")
    severity: str = Field(description="Severity level (Crítico, Alto, Medio, Bajo)")
    subtasks: List[str] = Field(description="List of specific subtasks to perform")


class TaskRankingOutput(BaseModel):
    """Output from ranking investigation tasks"""
    ranked_tasks: List[RankedTask] = Field(
        description=(
            "Top 5 tasks ranked by priority. Each task MUST include ALL fields from the input: "
            "id, code, name, desc, where_to_look, severity, and subtasks. "
            "Return the exact task data you received, just reordered by priority."
        )
    )
    ranking_rationale: str = Field(description="Explanation of ranking criteria and order")


class TaskClassificationOutput(BaseModel):
    """Output from classifying feasible investigation tasks"""
    feasible_task_ids: List[int] = Field(
        description=(
            "List of task IDs that are FEASIBLE to validate given available data. "
            "Include tasks where we have sufficient documents and information to perform validation. "
            "Can include anywhere from 5-11 task IDs depending on data availability. "
            "Only exclude tasks that are completely impossible due to missing critical data."
        )
    )
    classification_rationale: str = Field(
        description=(
            "Explanation of classification criteria. "
            "For each excluded task, explain WHY it's not feasible (missing documents, insufficient data, etc.). "
            "For included tasks, briefly note what makes them feasible."
        )
    )


class TaskInvestigationOutput(BaseModel):
    """Output from investigating a single task"""
    task_id: int = Field(description="Task ID")
    task_code: str = Field(description="Task code (H-01, H-02, etc.)")
    task_name: str = Field(description="Task name/description")
    validation_passed: bool = Field(description="Whether the task validation passed")
    findings: List[Anomaly] = Field(description="Anomalies/issues found during investigation")
    investigation_summary: str = Field(description="Summary of the investigation")


class SummaryOutput(BaseModel):
    """Output from the Summary Agent - agentic analysis of all investigation results"""
    executive_summary: str = Field(
        description=(
            "Executive summary in markdown format explaining: "
            "1) Overall risk level (BAJO/MEDIO/ALTO/CRÍTICO), "
            "2) Main conclusion about fraud indicators, "
            "3) Key correlated findings across tasks that suggest fraud patterns"
        )
    )
    detailed_analysis: str = Field(
        description=(
            "Detailed analysis in markdown format with: "
            "1) Each investigated task (code, name, status), "
            "2) All anomalies found with evidence, confidence scores, "
            "3) Cross-references between related findings"
        )
    )
