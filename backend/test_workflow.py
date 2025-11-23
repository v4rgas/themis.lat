#!/usr/bin/env python3
"""
Test file for the LangGraph Fraud Detection Workflow
"""
import json
from datetime import datetime
from app.workflow import FraudDetectionWorkflow, detect_fraud
from app.schemas import RankingInput


def test_basic_workflow():
    """Test the basic workflow with a single tender"""
    print("=" * 60)
    print("TESTING BASIC FRAUD DETECTION WORKFLOW")
    print("=" * 60)

    # Create test input
    input_data = RankingInput(
        tender_id="TEST-2024-001",
        tender_name="Adquisición de Equipamiento Informático Municipal",
        tender_date="2024-01-15",
        bases="""
        La Municipalidad requiere la adquisición de 50 computadores de escritorio
        para renovación de equipamiento en oficinas municipales.

        Requisitos generales:
        - Entrega dentro de 30 días
        - Garantía mínima de 3 años
        - Soporte técnico local
        - Pago a 30 días desde recepción conforme
        """,
        bases_tecnicas="""
        Especificaciones técnicas obligatorias:
        - Procesador: Intel Core i7-12700K específicamente (no se aceptan equivalentes)
        - RAM: 32GB DDR5-5600 marca Kingston modelo KF556C40BBK2-32
        - Almacenamiento: SSD Samsung 980 PRO 1TB M.2 NVMe
        - Tarjeta gráfica: NVIDIA GeForce RTX 3060 Ti
        - Monitor: Dell UltraSharp U2722D 27" QHD (modelo exacto requerido)
        - Certificación: Requiere certificación PropTech-2000 (disponible solo de TechCorp)
        - Sistema operativo: Windows 11 Pro con licencia corporativa TechCorp

        Período de publicación: 3 días hábiles
        Modalidad: Licitación pública
        """,
        additional_context={
            "estimated_amount": 150000000,  # 150 million CLP
            "buyer": "Municipalidad de Santiago",
            "category": "Tecnología",
            "publication_date": "2024-01-10",
            "closing_date": "2024-01-13"
        }
    )

    # Initialize workflow
    workflow = FraudDetectionWorkflow(
        ranking_model="claude-haiku-4-5",
        detection_model="claude-haiku-4-5",
        temperature=0.7
    )

    # Run workflow
    print("\n🚀 Starting workflow execution...")
    result = workflow.run(input_data)

    # Display results
    print("\n" + "=" * 60)
    print("WORKFLOW RESULTS")
    print("=" * 60)

    print(f"\n📊 Summary:")
    print(result["workflow_summary"])

    if result["confirmed_fraud_cases"]:
        print(f"\n🚨 FRAUD CASES DETECTED: {len(result['confirmed_fraud_cases'])}")

        for case in result["confirmed_fraud_cases"]:
            print(f"\n📁 Tender ID: {case.tender_id}")
            print(f"   Status: {'FRAUDULENT' if case.is_fraudulent else 'CLEAN'}")
            print(f"   Summary: {case.investigation_summary}")

            if case.anomalies:
                print(f"\n   Anomalies found ({len(case.anomalies)}):")
                for i, anomaly in enumerate(case.anomalies, 1):
                    print(f"\n   {i}. {anomaly.anomaly_name}")
                    print(f"      Description: {anomaly.description}")
                    print(f"      Confidence: {anomaly.confidence:.2f}")
                    if anomaly.evidence:
                        print(f"      Evidence:")
                        for evidence in anomaly.evidence[:3]:  # Show first 3
                            print(f"        - {evidence}")
                    if anomaly.affected_documents:
                        print(f"      Documents: {', '.join(anomaly.affected_documents)}")
    else:
        print("\n✅ No fraud cases detected")

    print("\n" + "=" * 60)


def test_streaming_workflow():
    """Test the streaming capability of the workflow"""
    print("\n" + "=" * 60)
    print("TESTING STREAMING WORKFLOW")
    print("=" * 60)

    # Create test input
    input_data = RankingInput(
        tender_id="TEST-2024-002",
        tender_name="Servicio de Mantención de Áreas Verdes",
        tender_date="2024-02-01",
        bases="""
        Servicio de mantención de áreas verdes en parques municipales.
        Duración: 12 meses
        Superficie total: 50,000 m2
        """,
        bases_tecnicas="""
        - Corte de césped quincenal
        - Poda de árboles trimestral
        - Riego automático
        - Personal mínimo: 10 trabajadores
        - Experiencia mínima: 5 años en servicios similares
        """,
        additional_context={
            "estimated_amount": 50000000,
            "buyer": "Municipalidad de Providencia",
            "category": "Servicios"
        }
    )

    # Initialize workflow
    workflow = FraudDetectionWorkflow()

    # Stream execution
    print("\n🚀 Starting streaming execution...")
    for update in workflow.stream(input_data):
        print(f"📡 State update received: {list(update.keys())}")


def test_convenience_function():
    """Test the convenience function for quick fraud detection"""
    print("\n" + "=" * 60)
    print("TESTING CONVENIENCE FUNCTION")
    print("=" * 60)

    # Use convenience function
    fraud_cases = detect_fraud(
        tender_id="TEST-2024-003",
        tender_name="Compra de Medicamentos",
        tender_date="2024-03-01",
        bases="Adquisición de medicamentos para hospital regional",
        bases_tecnicas="""
        Medicamentos requeridos:
        - Paracetamol 500mg: 10,000 unidades
        - Ibuprofeno 400mg: 5,000 unidades
        - Medicamento XYZ-9000 (fabricado exclusivamente por PharmaCorp)
        - Entrega: 5 días hábiles
        - Publicación: 2 días
        """,
        additional_context={
            "amount": 80000000,
            "urgency": "high",
            "single_bidder_expected": True
        }
    )

    print(f"\n🔍 Quick scan found {len(fraud_cases)} potential fraud cases")
    for case in fraud_cases:
        print(f"  - {case.tender_id}: {len(case.anomalies)} anomalies")


def main():
    """Run all tests"""
    print("\n🏁 STARTING FRAUD DETECTION WORKFLOW TESTS\n")

    try:
        # Test 1: Basic workflow
        test_basic_workflow()

        # Test 2: Streaming workflow
        # test_streaming_workflow()  # Uncomment to test streaming

        # Test 3: Convenience function
        # test_convenience_function()  # Uncomment to test convenience function

        print("\n✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()