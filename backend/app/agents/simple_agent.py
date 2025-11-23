"""
Simple Agent - Procurement fraud investigation agent using LangChain v1 API
"""

from typing import Dict, Any, List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.config import settings
from app.prompts import simple_agent
from app.tools.get_plan import get_plan
from app.tools.read_buyer_attachments_table import read_buyer_attachments_table
from app.tools.read_buyer_attachment_doc import read_buyer_attachment_doc
from app.tools.read_award_result import read_award_result
from app.tools.read_award_result_attachment_doc import read_award_result_attachment_doc


class AnomalyOutput(BaseModel):
    """Structured output for anomaly detection in procurement analysis"""

    anomalies: List[str] = Field(
        description="List of detected anomalies or red flags in the procurement process"
    )


class SimpleAgent:
    """
    Procurement fraud investigation agent using LangChain v1's create_agent API.

    This agent investigates flagged public procurement tenders from Mercado Público (Chile).
    It uses specialized tools to analyze tender documents and identify anomalies that may
    indicate fraud or corruption.

    Available tools:
    - get_plan: Creates investigation plans
    - read_buyer_attachments_table: Lists tender documents
    - read_buyer_attachment_doc: Extracts text from PDF documents
    - read_award_result: Retrieves award decision and results

    Usage:
        agent = SimpleAgent()
        response = agent.run("Investigate tender 1234-56-LR22: single bidder, 3-day publication, IT services")
        print(response.anomalies)  # ['Overly specific technical requirements...', ...]
    """

    def __init__(
        self,
        model_name: str = "google/gemini-2.5-flash-lite-preview-09-2025",
        temperature: float = 0.7,
    ):
        """
        Initialize the Procurement Fraud Investigation Agent using LangChain v1 create_agent API.

        Args:
            model_name: Anthropic model to use
            temperature: Temperature for model responses (0.0-1.0, recommend 0.7 for balanced analysis)
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

        # Define investigation tools
        tools = [
            get_plan,
            read_buyer_attachments_table,
            read_buyer_attachment_doc,
            read_award_result,
            read_award_result_attachment_doc,
        ]

        # Create investigation agent with structured output for anomaly detection
        self.agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=simple_agent.SYS_PROMPT,
            response_format=ToolStrategy(AnomalyOutput),
        )

    def run(self, message: str) -> AnomalyOutput:
        """
        Investigate a flagged tender and return detected anomalies.

        The agent will:
        1. Create an investigation plan using get_plan
        2. List available tender documents
        3. Analyze document contents for fraud indicators
        4. Return structured list of anomalies with evidence

        Args:
            message: Tender description including ID and initial red flags
                    Format: "Investigate tender [ID]: [red flags], [tender type/category]"

        Returns:
            AnomalyOutput: Structured output with list of detected anomalies

        Example:
            >>> agent = SimpleAgent()
            >>> response = agent.run("Investigate tender 1234-56-LR22: single bidder, 3-day publication, IT services")
            >>> print(response.anomalies)
            ['Technical specifications require exact model ABC-2000, eliminating alternatives',
             'Publication period of 3 days violates legal minimum of 20 days for LR category',
             'Evaluation criteria awards 50% to proprietary certification only available from one supplier']
        """
        result = self.agent.invoke({"messages": [{"role": "user", "content": message}]})

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

    def _extract_response(self, result: Dict[str, Any]) -> str:
        """
        Extract the text response from the agent's result.

        Args:
            result: The raw result from agent.invoke()

        Returns:
            str: The extracted text response
        """
        # The response is in the "messages" list, get the last AI message
        if "messages" in result:
            messages = result["messages"]
            if messages:
                # Get the last message content
                last_message = messages[-1]
                if hasattr(last_message, "content"):
                    return last_message.content
                elif isinstance(last_message, dict) and "content" in last_message:
                    return last_message["content"]

        # Fallback: try to convert result to string
        return str(result)
