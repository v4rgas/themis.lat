"""
Test script for PlanAgent - Testing anomaly detection in procurement/bidding processes
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.agents.plan_agent import PlanAgent


def test_plan_agent():
    """Test the PlanAgent with procurement anomaly detection requests."""

    print("=" * 80)
    print("TESTING PLAN AGENT - PROCUREMENT ANOMALY DETECTION")
    print("=" * 80)

    # Initialize the agent
    print("\n[1/4] Initializing PlanAgent...")
    agent = PlanAgent()
    print("✓ Agent initialized successfully")

    # Test cases focused on procurement anomaly detection
    test_requests = [
        "Analizar una licitación pública para detectar posibles irregularidades en los montos y participantes",
        "Investigar patrones sospechosos de adjudicación entre una empresa y entidades públicas en los últimos 2 años",
        "Detectar anomalías en el proceso de licitación: tiempos inusuales, montos inflados, y proveedores relacionados",
    ]

    for i, request in enumerate(test_requests, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i+1}/{len(test_requests)+1}] Test Case {i}: Anomaly Detection Scenario")
        print(f"{'=' * 80}")
        print(f"User Request: {request}")
        print("-" * 80)

        try:
            # Generate plan
            result = agent.run(request)

            # Display results
            print(f"\n✓ Plan generated successfully!")
            print(f"\nTotal Tasks: {len(result.tasks)}")
            print("\nGenerated Investigation Plan:")
            for idx, task in enumerate(result.tasks, 1):
                print(f"\n  Task {idx}:")
                print(f"  {task}")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_plan_agent()
