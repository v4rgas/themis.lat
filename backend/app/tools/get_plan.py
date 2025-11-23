"""
Tool for generating structured task plans from user requests
"""
from pydantic import BaseModel, Field
from langchain.tools import tool

from app.agents.plan_agent import PlanAgent


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
    # Initialize the planning agent
    plan_agent = PlanAgent()

    # Generate the plan
    plan_output = plan_agent.run(user_request)

    # Return structured result
    return {
        "steps": plan_output.steps,
        "total_steps": len(plan_output.steps)
    }
