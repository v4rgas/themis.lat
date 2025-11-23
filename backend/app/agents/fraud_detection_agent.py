"""
Fraud Detection Agent - Deep investigation of individual tenders for fraud indicators
"""

from typing import Dict, Any
from typing_extensions import NotRequired

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import AgentState
from langchain.agents.structured_output import ToolStrategy

from app.config import settings
from app.prompts import fraud_detection_agent
from app.schemas import FraudDetectionInput, FraudDetectionOutput
from app.tools.get_plan import get_plan
from app.tools.read_buyer_attachments_table import read_buyer_attachments_table
from app.tools.read_buyer_attachment_doc import read_buyer_attachment_doc
from app.tools.read_award_result import read_award_result
from app.tools.read_award_result_attachment_doc import read_award_result_attachment_doc
from app.middleware import WebSocketStreamingMiddleware


# Custom state schema para pasar session_id y task_info al middleware
class FraudAgentState(AgentState):
    """Custom state schema que incluye session_id y task_info"""

    session_id: NotRequired[str]
    task_info: NotRequired[Dict[str, Any]]


class FraudDetectionAgent:
    """
    Deep procurement fraud investigation agent for individual tender analysis.

    This agent performs thorough investigation of a single tender flagged as high-risk,
    identifying and documenting specific anomalies that indicate fraud or corruption.

    Available tools:
    - get_plan: Creates detailed investigation plans
    - read_buyer_attachments_table: Lists all tender documents
    - read_buyer_attachment_doc: Extracts and analyzes document content
    - read_supplier_attachments: Analyzes supplier submissions
    - read_award: Checks award decisions and justifications

    Usage:
        agent = FraudDetectionAgent()
        input_data = FraudDetectionInput(
            tender_id="1234-56-LR22",
            risk_indicators=["Single bidder", "3-day publication"],
            full_context={"tender_name": "IT Services", "amount": 500000}
        )
        result = agent.run(input_data)
        for anomaly in result.anomalies:
            print(f"{anomaly.anomaly_name}: {anomaly.confidence}")
    """

    def __init__(
        self,
        model_name: str = "google/gemini-2.5-flash-lite-preview-09-2025",
        temperature: float = 0.7,
    ):
        """
        Initialize the Fraud Detection Agent.

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

        # Define comprehensive investigation tools
        tools = [
            get_plan,
            read_buyer_attachments_table,
            read_buyer_attachment_doc,
            read_award_result,
            read_award_result_attachment_doc,
        ]

        # Create fraud detection agent with structured output and middleware
        self.agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=fraud_detection_agent.SYS_PROMPT,
            response_format=ToolStrategy(FraudDetectionOutput),
            middleware=[WebSocketStreamingMiddleware()],
            state_schema=FraudAgentState,
        )

    def run(
        self,
        input_data: FraudDetectionInput,
        session_id: str = None,
        task_info: Dict[str, Any] = None,
    ) -> FraudDetectionOutput:
        """
        Perform deep fraud investigation on a single tender.

        The agent will:
        1. Create investigation plan based on risk indicators
        2. Systematically analyze all available documents
        3. Identify specific anomalies with evidence
        4. Determine if tender shows fraud indicators
        5. Return detailed findings with confidence scores

        Args:
            input_data: FraudDetectionInput with tender details and risk indicators

        Returns:
            FraudDetectionOutput: Investigation results with anomalies found

        Example:
            >>> agent = FraudDetectionAgent()
            >>> input_data = FraudDetectionInput(
            ...     tender_id="1234-56-LR22",
            ...     risk_indicators=["Single bidder", "Overly specific requirements"],
            ...     full_context={"name": "IT Services", "value": 500000, "buyer": "Municipality"}
            ... )
            >>> result = agent.run(input_data)
            >>> if result.is_fraudulent:
            ...     print(f"Found {len(result.anomalies)} fraud indicators")
            ...     for anomaly in result.anomalies:
            ...         print(f"- {anomaly.anomaly_name}: {anomaly.description}")
        """
        # Format the investigation request
        message = f"""Conduct deep fraud investigation for tender:

TENDER ID: {input_data.tender_id}

RISK INDICATORS FROM RANKING:
{chr(10).join(f"- {indicator}" for indicator in input_data.risk_indicators)}

FULL CONTEXT:
{self._format_context(input_data.full_context)}

INVESTIGATION REQUIREMENTS:
1. Thoroughly analyze all available documents
2. Focus on the risk indicators identified
3. Find concrete evidence of fraud or corruption
4. Document specific anomalies with references
5. Provide confidence scores for each finding

Investigate systematically and return detailed anomalies with evidence.
"""

        # Prepare state with messages and middleware data
        state = {"messages": [{"role": "user", "content": message}]}

        # Add session_id and task_info to state for middleware
        if session_id:
            state["session_id"] = session_id
        if task_info:
            state["task_info"] = task_info

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

    def _format_context(self, context: Dict[str, Any]) -> str:
        """
        Format the context dictionary for readable presentation.

        Args:
            context: Dictionary with tender context

        Returns:
            str: Formatted context string
        """
        if not context:
            return "No additional context provided"

        formatted = []
        for key, value in context.items():
            # Convert key from snake_case to Title Case
            display_key = key.replace("_", " ").title()
            formatted.append(f"{display_key}: {value}")

        return "\n".join(formatted)

    def investigate_batch(
        self, inputs: list[FraudDetectionInput]
    ) -> list[FraudDetectionOutput]:
        """
        Investigate multiple tenders sequentially.

        Note: This is a convenience method for sequential processing.
        For parallel processing, use the LangGraph workflow instead.

        Args:
            inputs: List of FraudDetectionInput objects

        Returns:
            list[FraudDetectionOutput]: Investigation results for each tender
        """
        results = []
        for input_data in inputs:
            try:
                result = self.run(input_data)
                results.append(result)
            except Exception as e:
                # Create error response
                import traceback

                print(f"Investigation failed for tender {input_data.tender_id}: {e}")
                traceback.print_exc()
                error_result = FraudDetectionOutput(
                    tender_id=input_data.tender_id,
                    is_fraudulent=False,
                    anomalies=[],
                    investigation_summary=f"Investigation failed: {str(e)}",
                )
                results.append(error_result)

        return results
