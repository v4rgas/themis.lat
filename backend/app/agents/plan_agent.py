"""
Plan Agent - Generates structured task plans from user requests using LangChain v1 API
"""
from typing import List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy

from app.config import settings
from app.prompts import plan_agent

class PlanOutput(BaseModel):
    """Structured output for plan generation"""
    tasks: List[str] =  Field(
        description="Detailed instruction for the agent to execute this task"
    )


class PlanAgent:
    """
    Agent that generates structured task plans using LangChain v1's create_agent API.

    This agent uses Anthropic's native structured output via ProviderStrategy for
    reliable and type-safe plan generation.

    Usage:
        agent = PlanAgent()
        result = agent.run("Build a REST API for user management")
        print(result.tasks)  # ['Create database schema', 'Implement user model', ...]
    """

    def __init__(
        self,
        model_name: str = "google/gemini-2.5-flash-preview-09-2025",
        temperature: float = 0.0,
    ):
        """
        Initialize the Plan Agent using LangChain v1 create_agent API.

        Args:
            model_name: Anthropic model to use
            temperature: Temperature for model responses (0.0 = deterministic)
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

        # Create agent with structured output using ProviderStrategy
        # This uses Anthropic's native structured output feature
        self.agent = create_agent(
            model=model,
            tools=[],  # No tools needed for planning
            system_prompt=plan_agent.SYS_PROMPT,
            response_format=ProviderStrategy(PlanOutput)
        )

    def run(self, message: str) -> PlanOutput:
        """
        Generate a structured plan from a user message.

        Args:
            message: The user's request or objective

        Returns:
            PlanOutput: Structured plan with list of tasks

        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": message}]
        })

        # The structured response is available in the "structured_response" key
        return result["structured_response"]