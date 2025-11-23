"""
Summary Agent - Agentic analysis and correlation of investigation results
"""

from typing import List, Dict, Any
from typing_extensions import NotRequired
import json

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import AgentState
from langchain.agents.structured_output import ToolStrategy

from app.config import settings
from app.prompts import summary_agent
from app.schemas import TaskInvestigationOutput, SummaryOutput
from app.middleware import WebSocketStreamingMiddleware


# Custom state schema para pasar session_id al middleware
class SummaryAgentState(AgentState):
    """Custom state schema que incluye session_id"""

    session_id: NotRequired[str]


class SummaryAgent:
    """
    Procurement fraud summary agent for analyzing and correlating investigation results.

    This agent receives the results of multiple parallel investigations and:
    - Identifies correlations between anomalies across different tasks
    - Determines fraud patterns from collective findings
    - Generates two-level summary: executive (conclusions) + detailed (evidence)

    Unlike investigation agents, this agent has NO tools - it only analyzes provided data.

    Usage:
        agent = SummaryAgent()
        task_results = [
            TaskInvestigationOutput(...),
            TaskInvestigationOutput(...),
            # ... more results
        ]
        summary = agent.run(task_results, session_id="session-123")
        print(summary.executive_summary)
        print(summary.detailed_analysis)
    """

    def __init__(
        self,
        model_name: str = "openai/gpt-oss-120b",
        temperature: float = 0.3,
    ):
        """
        Initialize the Summary Agent.

        Args:
            model_name: Model to use for analysis
            temperature: Temperature for model responses (0.3 = more focused, less creative)
        """
        self.model_name = model_name
        self.temperature = temperature

        # Initialize model
        model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )

        # Create summary agent with NO tools (only analyzes provided data)
        self.agent = create_agent(
            model=model,
            tools=[],  # No tools - agent only analyzes investigation results
            system_prompt=summary_agent.SYS_PROMPT,
            response_format=ToolStrategy(SummaryOutput),
            middleware=[WebSocketStreamingMiddleware()],
            state_schema=SummaryAgentState,
        )

    def run(
        self,
        task_results: List[TaskInvestigationOutput],
        session_id: str = None,
    ) -> SummaryOutput:
        """
        Generate comprehensive summary from investigation results.

        The agent will:
        1. Analyze all task results and their anomalies
        2. Identify correlations between findings across tasks
        3. Determine fraud patterns from collective evidence
        4. Generate executive summary with risk level and conclusions
        5. Generate detailed analysis with all evidence

        Args:
            task_results: List of TaskInvestigationOutput from parallel investigations
            session_id: Optional session ID for WebSocket streaming

        Returns:
            SummaryOutput: Two-level markdown summary (executive + detailed)

        Example:
            >>> agent = SummaryAgent()
            >>> results = [
            ...     TaskInvestigationOutput(task_id=1, task_code="H-01", ...),
            ...     TaskInvestigationOutput(task_id=2, task_code="H-02", ...),
            ... ]
            >>> summary = agent.run(results)
            >>> print(summary.executive_summary)
            # RESUMEN EJECUTIVO
            **Nivel de Riesgo**: ALTO
            ...
        """
        # Convert task results to JSON format for the prompt
        results_json = json.dumps(
            [result.model_dump() for result in task_results],
            indent=2,
            ensure_ascii=False
        )

        # Format the summary request
        message = f"""Analyze the following investigation results and generate a comprehensive summary.

INVESTIGATION RESULTS ({len(task_results)} tasks investigated):

```json
{results_json}
```

Generate a two-level summary:
1. **Executive Summary**: Correlations, fraud patterns, risk level, conclusions
2. **Detailed Analysis**: All tasks with full evidence and findings

Use markdown formatting for clarity and structure.
"""

        # Prepare state with messages
        state = {"messages": [{"role": "user", "content": message}]}

        # Add session_id to state for middleware
        if session_id:
            state["session_id"] = session_id

        result = self.agent.invoke(state)

        # Return the structured response
        if "structured_response" not in result:
            # Debug: Print available keys to understand the issue
            print(f"WARNING: structured_response not found in result. Available keys: {result.keys()}")
            # Raise a more informative error
            raise ValueError(
                f"Agent did not return structured_response. Available keys: {list(result.keys())}. "
                f"This may indicate the agent failed to complete successfully."
            )
        return result["structured_response"]
