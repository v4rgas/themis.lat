"""
Test script for get_plan tool - Testing procurement anomaly detection planning
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.tools.get_plan import get_plan


def test_get_plan_tool():
    """Test the get_plan tool with procurement anomaly detection scenarios."""

    print("=" * 80)
    print("TESTING GET_PLAN TOOL - PROCUREMENT ANOMALY DETECTION")
    print("=" * 80)

    # Display tool information
    print("\n[1/4] Tool Information:")
    print(f"  Name: {get_plan.name}")
    print(f"  Description: {get_plan.description[:100]}...")
    print(f"  Args Schema: {get_plan.args_schema.__name__}")

    # Test cases focused on procurement anomaly detection
    test_requests = [
        "Analizar licitación ID 12345-2024 para detectar montos sospechosos, tiempos irregulares y relaciones entre proveedores",
        "Investigar historial de adjudicaciones de la empresa 'Constructora XYZ' para encontrar patrones de favorecimiento",
        "Detectar anomalías en licitaciones de servicios de TI: sobrecostos, falta de competencia, y especificaciones restrictivas",
    ]

    for i, request in enumerate(test_requests, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i+1}/{len(test_requests)+1}] Test Case {i}: Anomaly Investigation")
        print(f"{'=' * 80}")
        print(f"Investigation Request: {request}")
        print("-" * 80)

        try:
            # Invoke the tool directly
            result = get_plan.invoke({"user_request": request})

            # Display results
            print(f"\n✓ Tool executed successfully!")
            print(f"\nResult Type: {type(result)}")
            print(f"Total Investigation Tasks: {result.get('total_tasks', 'N/A')}")
            print("\nInvestigation Plan:")

            tasks = result.get('tasks', [])
            for idx, task in enumerate(tasks, 1):
                print(f"\n  Step {idx}:")
                print(f"  {task}")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)

    # Display tool schema
    print("\n" + "=" * 80)
    print("TOOL SCHEMA (for LLM)")
    print("=" * 80)
    print("\nThis is what an LLM sees when deciding to use this tool:")
    print(f"\nTool Name: {get_plan.name}")
    print(f"\nDescription:\n{get_plan.description}")
    print(f"\nInput Schema:\n{get_plan.args_schema.model_json_schema()}")


if __name__ == "__main__":
    test_get_plan_tool()
