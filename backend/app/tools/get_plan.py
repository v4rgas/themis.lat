"""
Tool for generating structured task plans from user requests
"""
from pydantic import BaseModel, Field
from langchain.tools import tool

from app.agents.plan_agent import PlanAgent

# Global variable to store the API key for the current request context
# This is set by the FraudDetectionAgent before tool execution
_current_openrouter_api_key: str = None


def set_openrouter_api_key(api_key: str):
    """Set the OpenRouter API key for the current request context."""
    global _current_openrouter_api_key
    _current_openrouter_api_key = api_key


def get_openrouter_api_key() -> str:
    """Get the OpenRouter API key for the current request context."""
    global _current_openrouter_api_key
    if _current_openrouter_api_key is None:
        raise ValueError("OpenRouter API key not set. Call set_openrouter_api_key first.")
    return _current_openrouter_api_key


class GetPlanInput(BaseModel):
    """Input schema for the get_plan tool."""
    user_request: str = Field(
        description="The user's request or objective that needs to be broken down into a structured plan"
    )


@tool(args_schema=GetPlanInput)
def get_plan(user_request: str) -> dict:
    """Create investigation plan for tender analysis. Call this FIRST.

    Args:
        user_request: Tender details and red flags to investigate

    Returns:
        dict: List of investigation tasks
    """
    # Initialize the planning agent with the current API key
    api_key = get_openrouter_api_key()
    plan_agent = PlanAgent(openrouter_api_key=api_key)

    # Generate the plan
    plan_output = plan_agent.run(user_request)

    # Return structured result
    return {
        "steps": plan_output.steps,
        "total_steps": len(plan_output.steps)
    }
