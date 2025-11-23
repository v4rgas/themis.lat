"""
Ranking Agent - Ranks procurement tenders by fraud risk indicators
"""

from typing import Dict, Any
from typing_extensions import NotRequired

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import AgentState
from langchain.agents.structured_output import ToolStrategy

from app.config import settings
from app.prompts import ranking_agent
from app.schemas import RankingInput, RankingOutput, TaskClassificationOutput
from app.tools.read_buyer_attachments_table import read_buyer_attachments_table
from app.tools.read_buyer_attachment_doc import read_buyer_attachment_doc
from app.tools.read_award_result import read_award_result
from app.tools.read_award_result_attachment_doc import read_award_result_attachment_doc
from app.middleware import WebSocketStreamingMiddleware


# Custom state schema para pasar session_id y task_info al middleware
class RankingAgentState(AgentState):
    """Custom state schema que incluye session_id y task_info"""

    session_id: NotRequired[str]
    task_info: NotRequired[Dict[str, Any]]


class RankingAgent:
    """
    Procurement risk ranking agent that analyzes tenders and ranks them by fraud likelihood.

    This agent evaluates tender contexts and identifies risk indicators to produce
    a ranked list of the top 5 most suspicious cases for deep investigation.

    Available tools:
    - read_buyer_attachments_table: Lists tender documents
    - read_buyer_attachment_doc: Analyzes document content

    Usage:
        agent = RankingAgent()
        input_data = RankingInput(
            tender_id="1234-56-LR22",
            tender_name="IT Services Procurement",
            tender_date="2024-01-15",
            bases="General requirements...",
            bases_tecnicas="Technical specifications..."
        )
        result = agent.run(input_data)
        for item in result.ranked_items:
            print(f"{item.tender_id}: Risk Score {item.risk_score}")
    """

    def __init__(
        self,
        model_name: str = "google/gemini-2.5-flash-lite-preview-09-2025",
        temperature: float = 0.7,
    ):
        """
        Initialize the Ranking Agent.

        Args:
            model_name: Anthropic model to use
            temperature: Temperature for model responses (0.0-1.0)
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

        # Define tools for risk assessment
        tools = [
            read_buyer_attachments_table,
            read_buyer_attachment_doc,
            read_award_result,
            read_award_result_attachment_doc,
        ]

        # Create ranking agent with structured output and middleware
        self.agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=ranking_agent.SYS_PROMPT,
            response_format=ToolStrategy(TaskClassificationOutput),
            middleware=[WebSocketStreamingMiddleware()],
            state_schema=RankingAgentState,
        )

    def run(
        self, input_data: RankingInput, session_id: str = None
    ) -> TaskClassificationOutput:
        """
        Analyze tender context and classify which investigation tasks are feasible.

        The agent will:
        1. Analyze the tender context (name, date, bases, technical specs)
        2. Check document availability using tools
        3. Assess data completeness for each task
        4. Filter out tasks that lack necessary data
        5. Return list of feasible task IDs (5-11 tasks)

        Args:
            input_data: RankingInput with tender context
            session_id: Optional session ID for WebSocket streaming

        Returns:
            TaskClassificationOutput: List of feasible task IDs with rationale

        Example:
            >>> agent = RankingAgent()
            >>> input_data = RankingInput(
            ...     tender_id="1234-56-LR22",
            ...     tender_name="Computer Equipment",
            ...     tender_date="2024-01-15",
            ...     bases="Supply 50 computers for municipal offices",
            ...     bases_tecnicas="Intel Core i7-12700, 16GB RAM, specific model required"
            ... )
            >>> result = agent.run(input_data)
            >>> print(result.feasible_task_ids)
            [1, 2, 3, 4, 5, 7, 8, 9, 11]
        """
        # Format the message with tender context
        message = f"""Classify which investigation tasks are FEASIBLE to validate for this tender:

Tender ID: {input_data.tender_id}
Tender Name: {input_data.tender_name}
Date: {input_data.tender_date}

Bases (General Requirements):
{input_data.bases}

Bases Técnicas (Technical Specifications):
{input_data.bases_tecnicas}

Additional Context: {input_data.additional_context}

Please classify which investigation tasks are feasible given the available data.
Return ONLY the IDs of tasks that can be validated (5-11 tasks).
Focus on filtering OUT tasks that are impossible due to missing critical data or documents.
"""

        # Prepare state with messages and middleware data
        state = {"messages": [{"role": "user", "content": message}]}

        # Add session_id to state for middleware
        if session_id:
            state["session_id"] = session_id
            state["task_info"] = {"name": "Clasificación de tareas factibles"}

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

    def run_batch(self, tenders: list[RankingInput]) -> RankingOutput:
        """
        Analyze multiple tenders and return top 5 highest risk across all.

        Args:
            tenders: List of RankingInput objects to analyze

        Returns:
            RankingOutput: Top 5 highest risk items across all tenders
        """
        # Create a batch message with all tenders
        message = "Analyze the following tenders and rank the TOP 5 highest fraud risk items across ALL of them:\n\n"

        for i, tender in enumerate(tenders, 1):
            message += f"""
=== Tender {i} ===
ID: {tender.tender_id}
Name: {tender.tender_name}
Date: {tender.tender_date}

Bases: {tender.bases}

Bases Técnicas: {tender.bases_tecnicas}

Additional Context: {tender.additional_context}
"""

        message += """

Analyze ALL tenders above and return a single ranking of the TOP 5 items with highest fraud risk.
The ranking should compare risk across all provided tenders, not just within each tender."""

        result = self.agent.invoke({"messages": [{"role": "user", "content": message}]})

        if "structured_response" not in result:
            # Debug: Print available keys to understand the issue
            print(f"WARNING: structured_response not found in result. Available keys: {result.keys()}")
            # Raise a more informative error
            raise ValueError(
                f"Agent did not return structured_response. Available keys: {list(result.keys())}. "
                f"This may indicate the agent failed to complete successfully."
            )
        return result["structured_response"]
