"""
LangGraph Workflow for Fraud Detection - Orchestrates ranking and parallel investigation
"""

from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict
import uuid
import asyncio
import traceback
from datetime import datetime
from operator import add
import os
import glob
import tempfile
import logging

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send, Command
from langchain_core.messages import HumanMessage, AIMessage

from app.agents.ranking_agent import RankingAgent
from app.agents.fraud_detection_agent import FraudDetectionAgent
from app.agents.summary_agent import SummaryAgent
from app.schemas import (
    RankingInput,
    RankingOutput,
    RankedItem,
    FraudDetectionInput,
    FraudDetectionOutput,
    Anomaly,
    SummaryOutput,
)
from app.utils.get_tender import get_tender, TenderResponse
from app.utils.build_ranking_input import (
    build_ranking_input,
    fetch_and_extract_documents,
)
from app.investigation_tasks import INVESTIGATION_TASKS, InvestigationTask
from app.schemas import TaskClassificationOutput, TaskInvestigationOutput
from app.utils.websocket_manager import manager


class WorkflowState(TypedDict):
    """State definition for the fraud detection workflow"""

    # Input
    tender_id: str
    session_id: Optional[str]  # For WebSocket streaming

    # Fetched tender data
    tender_response: TenderResponse
    tender_documents: List[Dict[str, Any]]

    # Investigation tasks
    investigation_tasks: List[InvestigationTask]
    ranked_tasks: List[InvestigationTask]

    # Processed input for ranking (tender context)
    input_data: RankingInput

    # Task investigation results (accumulated from parallel processing)
    task_investigation_results: Annotated[List[TaskInvestigationOutput], add]

    # Final output (ordered by task id)
    tasks_by_id: List[TaskInvestigationOutput]
    workflow_summary: str

    # Error tracking
    errors: Annotated[List[str], add]


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
        ranking_model: str = "google/gemini-2.5-flash-lite-preview-09-2025",
        detection_model: str = "google/gemini-2.5-flash-lite-preview-09-2025",
        temperature: float = 0.7,
    ):
        """
        Initialize the workflow with agent configurations.

        Args:
            ranking_model: Model for ranking agent
            detection_model: Model for detection agents
            temperature: Temperature for all agents
        """
        self.ranking_agent = RankingAgent(
            model_name=ranking_model, temperature=temperature
        )
        self.detection_model = detection_model
        self.temperature = temperature

        # Build the workflow graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()

    def _send_log(
        self, session_id: Optional[str], message: str, task_code: Optional[str] = None
    ):
        """
        Send a log message via WebSocket if session_id is provided.

        This is a synchronous wrapper that handles async WebSocket communication internally.

        Args:
            session_id: Optional session ID for WebSocket streaming
            message: Log message to send
            task_code: Optional task code (e.g., "H-01") to associate this log with a specific task
        """
        if session_id:
            try:
                observation = {
                    "type": "log",
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                }
                if task_code:
                    observation["task_code"] = task_code

                asyncio.run(manager.send_observation(session_id, observation))
            except Exception as e:
                import traceback

                print(f"Failed to send log to WebSocket: {e}")
                traceback.print_exc()

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
        # Note: distribute_investigations uses Command/Send pattern, no direct edge needed
        # The investigate_task nodes will route to aggregate_results
        graph.add_edge("investigate_task", "aggregate_results")
        graph.add_edge("aggregate_results", END)

        return graph

    def _fetch_tender_data(self, state: WorkflowState) -> WorkflowState:
        """
        Fetch tender data node using get_tender() API.

        Retrieves tender metadata and documents, then builds RankingInput.
        """
        tender_id = state["tender_id"]
        session_id = state.get("session_id")

        self._send_log(session_id, f"Fetching tender data for {tender_id}...")
        print(f"Fetching tender data for {tender_id}...")

        try:
            # Fetch tender metadata from API
            self._send_log(session_id, "Retrieving tender metadata from API...")
            tender_response = asyncio.run(get_tender(tender_id))
            state["tender_response"] = tender_response

            self._send_log(
                session_id, f"Tender metadata fetched: {tender_response.name}"
            )
            print(f"Tender metadata fetched: {tender_response.name}")

            # Fetch and extract documents (first 3 documents, first 5 pages each)
            self._send_log(session_id, "Fetching tender documents...")
            print("Fetching tender documents...")
            tender_documents = fetch_and_extract_documents(
                tender_id, max_docs=3, session_id=session_id
            )
            state["tender_documents"] = tender_documents

            self._send_log(
                session_id, f"Successfully fetched {len(tender_documents)} documents"
            )
            print(f"Fetched {len(tender_documents)} documents")

            # Build RankingInput from fetched data
            self._send_log(session_id, "Processing tender data...")
            ranking_input = build_ranking_input(tender_response, tender_documents)
            state["input_data"] = ranking_input

            self._send_log(session_id, "Tender data processing complete")
            print("Tender data processing complete")

        except Exception as e:
            import traceback

            error_msg = f"Failed to fetch tender data: {str(e)}"
            self._send_log(session_id, f"ERROR: {error_msg}")
            self._send_log(
                session_id,
                "Creating minimal input to continue workflow with limited data",
            )
            self._send_log(
                session_id,
                "Note: Analysis will be less accurate due to missing tender data",
            )
            print(f"Error: {error_msg}")
            traceback.print_exc()
            state["errors"].append(error_msg)

            # Create minimal RankingInput to allow workflow to continue
            state["input_data"] = RankingInput(
                tender_id=tender_id,
                tender_name=f"Tender {tender_id}",
                tender_date="Unknown",
                bases="Error fetching tender data",
                bases_tecnicas="Error fetching tender data",
                additional_context={"error": str(e)},
            )

        return state

    def _load_investigation_tasks(self, state: WorkflowState) -> WorkflowState:
        """
        Load investigation tasks from pre-parsed list.

        Simply loads the INVESTIGATION_TASKS into state for ranking.
        """
        session_id = state.get("session_id")

        self._send_log(
            session_id, f"Loading {len(INVESTIGATION_TASKS)} investigation tasks..."
        )
        print(f"Loading {len(INVESTIGATION_TASKS)} investigation tasks...")

        state["investigation_tasks"] = INVESTIGATION_TASKS

        self._send_log(session_id, f"Tasks loaded. Ready for ranking.")
        print(f"Tasks loaded. Ready for ranking.")

        return state

    def _ranking_node(self, state: WorkflowState) -> WorkflowState:
        """
        Ranking node that prioritizes investigation tasks.

        Analyzes tender context and ranks investigation tasks by priority.
        """
        session_id = state.get("session_id")

        self._send_log(session_id, "Starting task ranking...")
        print("Starting task ranking...")

        try:
            # Prepare message for ranking agent
            tender_context = f"""
TENDER INFORMATION:
- ID: {state["input_data"].tender_id}
- Name: {state["input_data"].tender_name}
- Date: {state["input_data"].tender_date}
- Organization: {state["input_data"].additional_context.get("organization", "Unknown")}

AVAILABLE DOCUMENTS ({len(state["tender_documents"])}):
{chr(10).join(f"- {doc.get('name', 'Unknown')}" for doc in state["tender_documents"]) if state["tender_documents"] else "- No documents available"}

TENDER CONTEXT:
{state["input_data"].bases[:500]}...

INVESTIGATION TASKS TO RANK ({len(state["investigation_tasks"])}):
"""
            # Add all tasks
            for task in state["investigation_tasks"]:
                tender_context += f"""
Task {task["id"]} - {task["code"]}: {task["name"]}
- Description: {task["desc"]}
- Where to look: {task["where_to_look"]}
- Severity: {task["severity"]}
- Subtasks: {len(task["subtasks"])}
"""

            tender_context += """

Classify which tasks are FEASIBLE to validate given available data (5-11 tasks).
Return ONLY the IDs of feasible tasks. Focus on filtering OUT impossible tasks.
"""

            # Run ranking agent
            self._send_log(
                session_id, "Classification agent filtering feasible tasks..."
            )
            self._send_log(
                session_id,
                f"Assembling context: {len(state['investigation_tasks'])} tasks, {len(state['tender_documents'])} documents",
            )
            classification_result: TaskClassificationOutput = self.ranking_agent.run(
                RankingInput(
                    tender_id=state["input_data"].tender_id,
                    tender_name=state["input_data"].tender_name,
                    tender_date=state["input_data"].tender_date,
                    bases=tender_context,
                    bases_tecnicas="",
                    additional_context={},
                ),
                session_id=session_id,
            )
            self._send_log(
                session_id,
                f"Classification agent completed. Selected {len(classification_result.feasible_task_ids)} feasible tasks",
            )

            # Filter tasks from investigation_tasks using the feasible IDs
            feasible_ids = classification_result.feasible_task_ids
            state["ranked_tasks"] = [
                task
                for task in state["investigation_tasks"]
                if task["id"] in feasible_ids
            ]

            self._send_log(
                session_id,
                f"Task classification complete. {len(state['ranked_tasks'])} feasible tasks selected:",
            )
            print(
                f"Task classification complete. {len(state['ranked_tasks'])} feasible tasks selected."
            )
            for i, task in enumerate(state["ranked_tasks"], 1):
                task_summary = (
                    f"#{i}: Task {task['id']} - {task['code']} ({task['name'][:60]}...)"
                )
                self._send_log(session_id, task_summary)
                print(
                    f"  {i}. Task {task['id']} ({task['code']}): {task['name'][:50]}..."
                )

        except Exception as e:
            import traceback

            self._send_log(session_id, f"ERROR: Task classification failed - {str(e)}")
            self._send_log(
                session_id, "Using fallback strategy: selecting first 5 tasks by ID"
            )
            self._send_log(
                session_id,
                "Warning: Results may be less accurate due to ranking failure",
            )
            print(f"Task ranking failed: {e}")
            traceback.print_exc()
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
        session_id = state.get("session_id")

        self._send_log(
            session_id,
            f"Launching {len(state['ranked_tasks'])} parallel task investigations...",
        )
        print(f"Launching {len(state['ranked_tasks'])} parallel task investigations...")

        # Create Send commands for each ranked task
        send_commands = []

        for idx, task in enumerate(state["ranked_tasks"]):
            # Prepare input for task investigation
            task_id = task.get("id", idx)  # Use index as fallback

            # Log each task being queued
            self._send_log(
                session_id,
                f"Queuing investigation {idx + 1}/{len(state['ranked_tasks'])}: Task {task['id']} - {task['code']}",
            )

            task_input = {
                "task": task,
                "tender_context": state["input_data"],
                "tender_documents": state["tender_documents"],
                "investigation_id": f"task_{task['id']}_{uuid.uuid4().hex[:8]}",
                "session_id": session_id,  # Pass session_id to child nodes
            }

            # Create Send command to investigate_task node
            send_commands.append(Send("investigate_task", task_input))

        # Return Command with all Send operations
        return Command(goto=send_commands, update=state)

    def _investigate_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Investigation node that validates a specific task.

        This node is called in parallel for each ranked task.
        Returns state update dictionary to accumulate results.
        """
        task = inputs.get("task")
        investigation_id = inputs.get("investigation_id", "unknown")
        session_id = inputs.get("session_id")

        # Extract task_code at the start and store it locally for all logs in this execution context
        task_code = task.get("code", "Unknown") if task else "Unknown"

        self._send_log(
            session_id,
            f"Investigation {investigation_id} starting for Task {task['id']} ({task_code})...",
            task_code=task_code,
        )
        print(
            f"Investigation {investigation_id} starting for Task {task['id']} ({task_code})..."
        )

        try:
            # Create fraud detection agent
            agent = FraudDetectionAgent(
                model_name=self.detection_model, temperature=self.temperature
            )

            # Prepare message for investigation
            tender_context = inputs.get("tender_context")
            task_id = task.get("id", 0)
            task_name = task.get("name", "Unknown task")
            task_desc = task.get("desc", "No description")
            task_where = task.get("where_to_look", "Not specified")
            task_severity = task.get("severity", "Unknown")
            task_subtasks = task.get("subtasks", [])

            # Log subtask information
            self._send_log(
                session_id,
                f"Task {task_id}: Validating {len(task_subtasks)} subtasks",
                task_code=task_code,
            )

            message = f"""
INVESTIGATION TASK:

Task ID: {task_id}
Task Code: {task_code}
Task Name: {task_name}

WHAT TO VALIDATE:
{task_desc}

WHERE TO LOOK:
{task_where}

SEVERITY: {task_severity}

SUBTASKS:
{chr(10).join(f"{i + 1}. {subtask}" for i, subtask in enumerate(task_subtasks))}

TENDER CONTEXT:
- Tender ID: {tender_context.tender_id}
- Tender Name: {tender_context.tender_name}
- Organization: {tender_context.additional_context.get("organization", "Unknown")}

AVAILABLE DOCUMENTS:
{chr(10).join(f"- {doc.get('name', 'Unknown')}" for doc in inputs.get("tender_documents", []))}

TENDER INFORMATION:
{tender_context.bases[:1000]}...

Please investigate this task systematically and report your findings.
"""

            # Run investigation (reusing FraudDetectionAgent but with task-based input)
            self._send_log(
                session_id,
                f"Task {task['id']}: Agent starting deep investigation...",
                task_code=task_code,
            )
            detection_input = FraudDetectionInput(
                tender_id=tender_context.tender_id,
                risk_indicators=[task_name],
                full_context={"task": task, "message": message},
            )

            result = agent.run(
                detection_input,
                session_id=session_id,
                task_info={"id": task_id, "code": task_code, "name": task_name},
            )

            # Log agent completion
            self._send_log(
                session_id,
                f"Task {task['id']}: Agent completed. Found {len(result.anomalies)} anomalies",
                task_code=task_code,
            )

            # Convert to TaskInvestigationOutput
            task_result = TaskInvestigationOutput(
                task_id=task_id if isinstance(task_id, int) else 0,
                task_code=task_code,
                task_name=task_name,
                validation_passed=not result.is_fraudulent,  # Inverse: fraud detected = validation failed
                findings=result.anomalies,
                investigation_summary=result.investigation_summary,
            )

            self._send_log(
                session_id,
                f"Task {task['id']} investigation complete. Validation passed: {task_result.validation_passed}",
                task_code=task_code,
            )
            print(
                f"Task {task['id']} investigation complete. Validation passed: {task_result.validation_passed}"
            )

            # Return state update - this will be accumulated via the 'add' reducer
            return {"task_investigation_results": [task_result]}

        except Exception as e:
            import traceback

            error_msg = f"{type(e).__name__}: {str(e)}"
            self._send_log(
                session_id,
                f"ERROR: Task {task['id']} investigation failed - {error_msg}",
                task_code=task_code,
            )
            self._send_log(
                session_id,
                f"Task {task['id']}: Marking investigation as failed",
                task_code=task_code,
            )
            print(f"Task {task['id']} investigation failed: {e}")
            traceback.print_exc()
            # Return error result
            error_result = TaskInvestigationOutput(
                task_id=task.get("id", 0),
                task_code=task.get("code", "Unknown"),
                task_name=task.get("name", "Unknown task"),
                validation_passed=False,
                findings=[],
                investigation_summary=f"Investigation failed: {error_msg}",
            )
            return {"task_investigation_results": [error_result]}

    def _cleanup_temp_files(self, tender_id: str, session_id: Optional[str] = None):
        """
        Clean up old cache files (age-based cleanup).

        Instead of deleting files immediately after workflow completion, this performs
        age-based cleanup of cache files older than 24 hours. This allows cache reuse
        across multiple workflow runs while preventing unbounded cache growth.

        Cache files (OCR results, HTML pages, documents) are preserved for reuse
        in subsequent workflows, significantly reducing API calls and improving performance.

        Args:
            tender_id: Tender ID (preserved for compatibility, but not used for cleanup)
            session_id: Optional session ID for WebSocket streaming
        """
        self._send_log(session_id, "Performing cache cleanup (removing files >24h old)...")

        try:
            from app.utils.cache_manager import get_cache_manager

            cache = get_cache_manager()

            # Get cache stats before cleanup
            stats_before = cache.get_cache_stats()

            # Clean up files older than 24 hours
            cache.cleanup_old_cache(max_age_hours=24)

            # Get cache stats after cleanup
            stats_after = cache.get_cache_stats()

            # Calculate what was removed
            ocr_removed = stats_before['ocr_files'] - stats_after['ocr_files']
            html_removed = stats_before['html_files'] - stats_after['html_files']
            docs_removed = stats_before['docs_files'] - stats_after['docs_files']

            total_removed = ocr_removed + html_removed + docs_removed

            if total_removed > 0:
                cleanup_msg = (
                    f"Cache cleanup: Removed {total_removed} old files "
                    f"(OCR: {ocr_removed}, HTML: {html_removed}, Docs: {docs_removed})"
                )
                logging.info(cleanup_msg)
                self._send_log(session_id, cleanup_msg)
                print(cleanup_msg)
            else:
                self._send_log(session_id, "Cache cleanup: No old files to remove")

            # Log current cache stats
            cache_info = (
                f"Cache stats: {stats_after['ocr_files']} OCR files ({stats_after['ocr_size_mb']:.1f}MB), "
                f"{stats_after['html_files']} HTML files ({stats_after['html_size_mb']:.1f}MB), "
                f"{stats_after['docs_files']} documents ({stats_after['docs_size_mb']:.1f}MB)"
            )
            logging.info(cache_info)

        except Exception as e:
            # Don't raise - cleanup failures shouldn't break the workflow
            import traceback

            logging.warning(f"Cache cleanup failed: {e}")
            traceback.print_exc()
            print(f"Warning: Cache cleanup failed: {e}")

    def _aggregate_results(self, state: WorkflowState) -> WorkflowState:
        """
        Aggregation node that collects all task investigation results.

        Orders results by task ID.
        """
        session_id = state.get("session_id")

        self._send_log(
            session_id,
            f"Aggregating {len(state.get('task_investigation_results', []))} task investigation results...",
        )
        print(
            f"Aggregating {len(state.get('task_investigation_results', []))} task investigation results..."
        )

        # Get all task results
        task_results = state.get("task_investigation_results", [])

        # Order by task_id
        self._send_log(session_id, f"Sorting {len(task_results)} results by task ID...")
        tasks_by_id = sorted(task_results, key=lambda x: x.task_id)

        state["tasks_by_id"] = tasks_by_id

        # Calculate summary statistics for logging
        total_investigated = len(task_results)
        failed_validations = sum(1 for r in task_results if not r.validation_passed)
        total_findings = sum(len(r.findings) for r in task_results)

        # Log summary statistics
        self._send_log(
            session_id,
            f"Summary: {failed_validations} failed, {total_investigated - failed_validations} passed, {total_findings} total findings",
        )

        # Generate agentic summary using SummaryAgent
        self._send_log(
            session_id,
            "Generating agentic summary with correlation analysis...",
        )
        print("\nGenerating agentic summary with correlation analysis...")

        try:
            summary_agent = SummaryAgent(
                model_name=self.model_name,
                temperature=0.3,  # Lower temperature for more focused analysis
            )
            summary_output: SummaryOutput = summary_agent.run(
                task_results=tasks_by_id,
                session_id=session_id,
            )

            # Combine executive summary and detailed analysis into workflow_summary
            state["workflow_summary"] = f"""{summary_output.executive_summary}

---

{summary_output.detailed_analysis}"""

            self._send_log(
                session_id,
                "Agentic summary generation complete.",
            )
            print("\nAgentic summary generation complete.")
            print(state["workflow_summary"])

        except Exception as e:
            # Fallback to simple summary if agent fails
            import traceback
            self._send_log(
                session_id,
                f"WARNING: Summary agent failed - {str(e)}. Using fallback summary.",
            )
            logging.warning(f"Summary agent failed: {e}")
            traceback.print_exc()

            # Generate simple fallback summary
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
                summary_lines.append(
                    f"\nTask {result.task_id} ({result.task_code}): {status}"
                )
                summary_lines.append(f"  {result.task_name}")
                if result.findings:
                    summary_lines.append(f"  Findings: {len(result.findings)}")
                    for finding in result.findings[:2]:  # Show first 2
                        summary_lines.append(f"    - {finding.anomaly_name}")

            state["workflow_summary"] = "\n".join(summary_lines)
            print(state["workflow_summary"])

        self._send_log(
            session_id,
            f"Workflow complete. {failed_validations}/{total_investigated} validations failed.",
        )
        print(
            f"\nWorkflow complete. {failed_validations}/{total_investigated} validations failed."
        )

        # Clean up temporary PDF files for this tender
        try:
            self._cleanup_temp_files(state.get("tender_id"), session_id)
        except Exception as e:
            # Don't let cleanup errors affect the workflow result
            import traceback

            self._send_log(session_id, f"Warning: Cleanup failed - {str(e)}")
            logging.warning(f"Cleanup failed but workflow completed successfully: {e}")
            traceback.print_exc()

        return state

    def run(self, tender_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the fraud detection workflow.

        Args:
            tender_id: Tender ID to investigate
            session_id: Optional session ID for WebSocket streaming

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
        # Log workflow initialization
        self._send_log(
            session_id, f"Starting fraud detection workflow for tender {tender_id}"
        )
        self._send_log(session_id, "Initializing workflow state...")

        # Initialize state with tender_id and session_id
        initial_state: WorkflowState = {
            "tender_id": tender_id,
            "session_id": session_id,
            "tender_response": None,
            "tender_documents": [],
            "investigation_tasks": [],
            "ranked_tasks": [],
            "input_data": None,
            "task_investigation_results": [],
            "tasks_by_id": [],
            "workflow_summary": "",
            "errors": [],
        }

        # Run the workflow
        result = self.app.invoke(initial_state)

        self._send_log(session_id, "Workflow execution complete. Returning results...")
        return result

    def stream(self, tender_id: str, session_id: Optional[str] = None):
        """
        Stream workflow execution for real-time monitoring.

        Args:
            tender_id: Tender ID to investigate
            session_id: Optional session ID for WebSocket streaming

        Yields:
            State updates as the workflow progresses
        """
        # Initialize state with tender_id and session_id
        initial_state: WorkflowState = {
            "tender_id": tender_id,
            "session_id": session_id,
            "tender_response": None,
            "tender_documents": [],
            "investigation_tasks": [],
            "ranked_tasks": [],
            "input_data": None,
            "task_investigation_results": [],
            "tasks_by_id": [],
            "workflow_summary": "",
            "errors": [],
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
