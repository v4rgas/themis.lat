"""
LangGraph Workflow for Fraud Detection - Orchestrates ranking and parallel investigation
"""
from typing import Annotated, List, Dict, Any
from typing_extensions import TypedDict
import uuid

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send, Command
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.ranking_agent import RankingAgent
from app.agents.fraud_detection_agent import FraudDetectionAgent
from app.schemas import (
    RankingInput,
    RankingOutput,
    RankedItem,
    FraudDetectionInput,
    FraudDetectionOutput,
    Anomaly
)
from app.utils.get_tender import get_tender, TenderResponse
from app.utils.build_ranking_input import build_ranking_input, fetch_and_extract_documents
from app.investigation_tasks import INVESTIGATION_TASKS, InvestigationTask
from app.schemas import TaskRankingOutput, TaskInvestigationOutput


class WorkflowState(TypedDict):
    """State definition for the fraud detection workflow"""
    # Input
    tender_id: str

    # Fetched tender data
    tender_response: TenderResponse
    tender_documents: List[Dict[str, Any]]

    # Investigation tasks
    investigation_tasks: List[InvestigationTask]
    ranked_tasks: List[InvestigationTask]

    # Processed input for ranking (tender context)
    input_data: RankingInput

    # Task investigation results (accumulated from parallel processing)
    task_investigation_results: Annotated[List[TaskInvestigationOutput], add_messages]

    # Final output (ordered by task id)
    tasks_by_id: List[TaskInvestigationOutput]
    workflow_summary: str

    # Error tracking
    errors: List[str]


class FraudDetectionWorkflow:
    """
    LangGraph workflow that coordinates fraud detection through ranking and parallel investigation.

    Workflow structure:
    1. Entry Node: RankingAgent analyzes tender and produces top 5 risk items
    2. Command & Send: Launches 5 parallel FraudDetectionAgents
    3. Investigation Nodes: Each agent investigates one tender in parallel
    4. Aggregation Node: Collects results and filters confirmed fraud cases
    5. Output: Returns all confirmed fraud cases with detailed anomalies

    Usage:
        workflow = FraudDetectionWorkflow()
        input_data = RankingInput(
            tender_id="1234-56-LR22",
            tender_name="IT Services",
            tender_date="2024-01-15",
            bases="General requirements...",
            bases_tecnicas="Technical specs..."
        )
        result = workflow.run(input_data)
        for case in result["confirmed_fraud_cases"]:
            print(f"Fraud detected in {case.tender_id}")
    """

    def __init__(
        self,
        ranking_model: str = "claude-haiku-4-5",
        detection_model: str = "claude-haiku-4-5",
        temperature: float = 0.7
    ):
        """
        Initialize the workflow with agent configurations.

        Args:
            ranking_model: Model for ranking agent
            detection_model: Model for detection agents
            temperature: Temperature for all agents
        """
        self.ranking_agent = RankingAgent(
            model_name=ranking_model,
            temperature=temperature
        )
        self.detection_model = detection_model
        self.temperature = temperature

        # Build the workflow graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow graph"""

        # Create the graph with state schema
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("fetch_tender_data", self._fetch_tender_data)
        graph.add_node("load_investigation_tasks", self._load_investigation_tasks)
        graph.add_node("ranking_node", self._ranking_node)
        graph.add_node("distribute_investigations", self._distribute_investigations)
        graph.add_node("investigate_task", self._investigate_task)
        graph.add_node("aggregate_results", self._aggregate_results)

        # Add edges
        graph.add_edge(START, "fetch_tender_data")
        graph.add_edge("fetch_tender_data", "load_investigation_tasks")
        graph.add_edge("load_investigation_tasks", "ranking_node")
        graph.add_edge("ranking_node", "distribute_investigations")
        graph.add_edge("distribute_investigations", "aggregate_results")
        graph.add_edge("aggregate_results", END)

        return graph

    def _fetch_tender_data(self, state: WorkflowState) -> WorkflowState:
        """
        Fetch tender data node using get_tender() API.

        Retrieves tender metadata and documents, then builds RankingInput.
        """
        tender_id = state["tender_id"]
        print(f"Fetching tender data for {tender_id}...")

        try:
            # Fetch tender metadata from API
            tender_response = get_tender(tender_id)
            state["tender_response"] = tender_response

            print(f"Tender metadata fetched: {tender_response.name}")

            # Fetch and extract documents (first 3 documents, first 5 pages each)
            print("Fetching tender documents...")
            tender_documents = fetch_and_extract_documents(tender_id, max_docs=3)
            state["tender_documents"] = tender_documents

            print(f"Fetched {len(tender_documents)} documents")

            # Build RankingInput from fetched data
            ranking_input = build_ranking_input(tender_response, tender_documents)
            state["input_data"] = ranking_input

            print("Tender data processing complete")

        except Exception as e:
            error_msg = f"Failed to fetch tender data: {str(e)}"
            print(f"Error: {error_msg}")
            state["errors"].append(error_msg)

            # Create minimal RankingInput to allow workflow to continue
            state["input_data"] = RankingInput(
                tender_id=tender_id,
                tender_name=f"Tender {tender_id}",
                tender_date="Unknown",
                bases="Error fetching tender data",
                bases_tecnicas="Error fetching tender data",
                additional_context={"error": str(e)}
            )

        return state

    def _load_investigation_tasks(self, state: WorkflowState) -> WorkflowState:
        """
        Load investigation tasks from pre-parsed list.

        Simply loads the INVESTIGATION_TASKS into state for ranking.
        """
        print(f"Loading {len(INVESTIGATION_TASKS)} investigation tasks...")

        state["investigation_tasks"] = INVESTIGATION_TASKS

        print(f"Tasks loaded. Ready for ranking.")

        return state

    def _ranking_node(self, state: WorkflowState) -> WorkflowState:
        """
        Ranking node that prioritizes investigation tasks.

        Analyzes tender context and ranks investigation tasks by priority.
        """
        print("Starting task ranking...")

        try:
            # Prepare message for ranking agent
            tender_context = f"""
TENDER INFORMATION:
- ID: {state['input_data'].tender_id}
- Name: {state['input_data'].tender_name}
- Date: {state['input_data'].tender_date}
- Organization: {state['input_data'].additional_context.get('organization', 'Unknown')}

AVAILABLE DOCUMENTS ({len(state['tender_documents'])}):
{chr(10).join(f"- {doc.get('name', 'Unknown')}" for doc in state['tender_documents']) if state['tender_documents'] else '- No documents available'}

TENDER CONTEXT:
{state['input_data'].bases[:500]}...

INVESTIGATION TASKS TO RANK ({len(state['investigation_tasks'])}):
"""
            # Add all tasks
            for task in state['investigation_tasks']:
                tender_context += f"""
Task {task['id']} - {task['code']}: {task['name']}
- Description: {task['desc']}
- Where to look: {task['where_to_look']}
- Severity: {task['severity']}
- Subtasks: {len(task['subtasks'])}
"""

            tender_context += """

Rank the TOP 5 tasks by priority. Consider document availability, severity, and feasibility.
Return the ranked tasks with rationale.
"""

            # Run ranking agent
            ranking_result: TaskRankingOutput = self.ranking_agent.run(RankingInput(
                tender_id=state['input_data'].tender_id,
                tender_name=state['input_data'].tender_name,
                tender_date=state['input_data'].tender_date,
                bases=tender_context,
                bases_tecnicas="",
                additional_context={}
            ))

            # Extract ranked tasks
            state["ranked_tasks"] = ranking_result.ranked_tasks[:5]  # Top 5

            print(f"Task ranking complete. Top {len(state['ranked_tasks'])} tasks selected.")
            for i, task in enumerate(state['ranked_tasks'], 1):
                print(f"  {i}. Task {task['id']} ({task['code']}): {task['name'][:50]}...")

        except Exception as e:
            print(f"Task ranking failed: {e}")
            state["errors"].append(f"Task ranking error: {str(e)}")
            # Fallback: use first 5 tasks
            state["ranked_tasks"] = state["investigation_tasks"][:5]
            print(f"Using fallback: first 5 tasks")

        return state

    def _distribute_investigations(self, state: WorkflowState) -> Command:
        """
        Distribution node using Command and Send pattern.

        Launches parallel task investigations for each ranked task.
        """
        print(f"Launching {len(state['ranked_tasks'])} parallel task investigations...")

        # Create Send commands for each ranked task
        send_commands = []

        for idx, task in enumerate(state["ranked_tasks"]):
            # Prepare input for task investigation
            task_input = {
                "task": task,
                "tender_context": state["input_data"],
                "tender_documents": state["tender_documents"],
                "investigation_id": f"task_{task['id']}_{uuid.uuid4().hex[:8]}"
            }

            # Create Send command to investigate_task node
            send_commands.append(
                Send(
                    "investigate_task",
                    task_input
                )
            )

        # Return Command with all Send operations
        return Command(
            goto=send_commands,
            update=state
        )

    def _investigate_task(self, inputs: Dict[str, Any]) -> TaskInvestigationOutput:
        """
        Investigation node that validates a specific task.

        This node is called in parallel for each ranked task.
        """
        task = inputs.get("task")
        investigation_id = inputs.get("investigation_id", "unknown")
        print(f"Investigation {investigation_id} starting for Task {task['id']} ({task['code']})...")

        try:
            # Create fraud detection agent
            agent = FraudDetectionAgent(
                model_name=self.detection_model,
                temperature=self.temperature
            )

            # Prepare message for investigation
            tender_context = inputs.get("tender_context")
            message = f"""
INVESTIGATION TASK:

Task ID: {task['id']}
Task Code: {task['code']}
Task Name: {task['name']}

WHAT TO VALIDATE:
{task['desc']}

WHERE TO LOOK:
{task['where_to_look']}

SEVERITY: {task['severity']}

SUBTASKS:
{chr(10).join(f"{i+1}. {subtask}" for i, subtask in enumerate(task['subtasks']))}

TENDER CONTEXT:
- Tender ID: {tender_context.tender_id}
- Tender Name: {tender_context.tender_name}
- Organization: {tender_context.additional_context.get('organization', 'Unknown')}

AVAILABLE DOCUMENTS:
{chr(10).join(f"- {doc.get('name', 'Unknown')}" for doc in inputs.get('tender_documents', []))}

TENDER INFORMATION:
{tender_context.bases[:1000]}...

Please investigate this task systematically and report your findings.
"""

            # Run investigation (reusing FraudDetectionAgent but with task-based input)
            detection_input = FraudDetectionInput(
                tender_id=tender_context.tender_id,
                risk_indicators=[task['name']],
                full_context={"task": task, "message": message}
            )

            result = agent.run(detection_input)

            # Convert to TaskInvestigationOutput
            task_result = TaskInvestigationOutput(
                task_id=task['id'],
                task_code=task['code'],
                task_name=task['name'],
                validation_passed=not result.is_fraudulent,  # Inverse: fraud detected = validation failed
                findings=result.anomalies,
                investigation_summary=result.investigation_summary
            )

            print(f"Task {task['id']} investigation complete. Validation passed: {task_result.validation_passed}")

            return task_result

        except Exception as e:
            print(f"Task {task['id']} investigation failed: {e}")
            # Return error result
            return TaskInvestigationOutput(
                task_id=task['id'],
                task_code=task['code'],
                task_name=task['name'],
                validation_passed=False,
                findings=[],
                investigation_summary=f"Investigation failed: {str(e)}"
            )

    def _aggregate_results(self, state: WorkflowState) -> WorkflowState:
        """
        Aggregation node that collects all task investigation results.

        Orders results by task ID.
        """
        print(f"Aggregating {len(state.get('task_investigation_results', []))} task investigation results...")

        # Get all task results
        task_results = state.get("task_investigation_results", [])

        # Order by task_id
        tasks_by_id = sorted(task_results, key=lambda x: x.task_id)

        state["tasks_by_id"] = tasks_by_id

        # Generate workflow summary
        total_investigated = len(task_results)
        failed_validations = sum(1 for r in task_results if not r.validation_passed)
        total_findings = sum(len(r.findings) for r in task_results)

        summary_lines = []
        summary_lines.append("=" * 60)
        summary_lines.append("INVESTIGATION WORKFLOW COMPLETE")
        summary_lines.append("=" * 60)
        summary_lines.append(f"Tasks investigated: {total_investigated}")
        summary_lines.append(f"Validations failed: {failed_validations}")
        summary_lines.append(f"Total findings: {total_findings}")
        summary_lines.append("")
        summary_lines.append("RESULTS BY TASK ID:")

        for result in tasks_by_id:
            status = "✓ PASSED" if result.validation_passed else "✗ FAILED"
            summary_lines.append(f"\nTask {result.task_id} ({result.task_code}): {status}")
            summary_lines.append(f"  {result.task_name}")
            if result.findings:
                summary_lines.append(f"  Findings: {len(result.findings)}")
                for finding in result.findings[:2]:  # Show first 2
                    summary_lines.append(f"    - {finding.anomaly_name}")

        state["workflow_summary"] = "\n".join(summary_lines)

        print(f"\nWorkflow complete. {failed_validations}/{total_investigated} validations failed.")
        print(state["workflow_summary"])

        return state

    def run(self, tender_id: str) -> Dict[str, Any]:
        """
        Execute the fraud detection workflow.

        Args:
            tender_id: Tender ID to investigate

        Returns:
            Dict containing:
            - tender_response: TenderResponse from API
            - tender_documents: List of fetched documents
            - input_data: Processed RankingInput
            - investigation_tasks: All available investigation tasks
            - ranked_tasks: Top 5 tasks selected for investigation
            - task_investigation_results: Results from parallel task investigations
            - tasks_by_id: Task results ordered by task ID
            - workflow_summary: Summary of the investigation
            - errors: List of errors encountered
        """
        # Initialize state with just tender_id
        initial_state: WorkflowState = {
            "tender_id": tender_id,
            "tender_response": None,
            "tender_documents": [],
            "investigation_tasks": [],
            "ranked_tasks": [],
            "input_data": None,
            "task_investigation_results": [],
            "tasks_by_id": [],
            "workflow_summary": "",
            "errors": []
        }

        # Run the workflow
        result = self.app.invoke(initial_state)

        return result

    def stream(self, tender_id: str):
        """
        Stream workflow execution for real-time monitoring.

        Args:
            tender_id: Tender ID to investigate

        Yields:
            State updates as the workflow progresses
        """
        # Initialize state with just tender_id
        initial_state: WorkflowState = {
            "tender_id": tender_id,
            "tender_response": None,
            "tender_documents": [],
            "investigation_tasks": [],
            "ranked_tasks": [],
            "input_data": None,
            "task_investigation_results": [],
            "tasks_by_id": [],
            "workflow_summary": "",
            "errors": []
        }

        # Stream the workflow execution
        for state in self.app.stream(initial_state):
            yield state


# Convenience function for quick execution
def detect_fraud(tender_id: str) -> List[TaskInvestigationOutput]:
    """
    Convenience function to run fraud detection on a tender.

    Automatically fetches tender data from the API, ranks investigation tasks,
    and runs the complete task-based investigation workflow.

    Args:
        tender_id: Tender identifier (e.g., "1234-56-LR22")

    Returns:
        List of task investigation results ordered by task ID

    Example:
        >>> task_results = detect_fraud("1234-56-LR22")
        >>> for result in task_results:
        ...     print(f"Task {result.task_code}: {'PASSED' if result.validation_passed else 'FAILED'}")
        ...     for finding in result.findings:
        ...         print(f"  - {finding.anomaly_name}: {finding.description}")
    """
    workflow = FraudDetectionWorkflow()
    result = workflow.run(tender_id)
    return result["tasks_by_id"]