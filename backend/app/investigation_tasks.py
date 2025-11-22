"""
Investigation tasks pre-parsed from to_invastigate_list.csv
Each task contains its subtasks already structured and ready to use.
"""
from typing import TypedDict, List


class InvestigationTask(TypedDict):
    """Investigation task with its subtasks"""
    id: int  # Sequential ID
    code: str  # Task code (H-01, H-02, etc.)
    name: str  # Task description
    desc: str  # What the agent should validate
    where_to_look: str  # Where to look for information
    severity: str  # Severity level (Crítico, Alto, Medio, Bajo)
    subtasks: List[str]  # List of subtask descriptions


INVESTIGATION_TASKS: List[InvestigationTask] = [
  {
    "id": 1,
    "code": "H-01",
    "name": "Existencia de Bases Administrativas y Bases Técnicas diferenciadas",
    "desc": "Verificar que existan documentos o secciones diferenciadas como Bases Administrativas y Bases Técnicas.",
    "where_to_look": "Anexos y contenido de Bases",
    "severity": "Alto",
    "subtasks": [
      "Identificar documentos o secciones equivalentes a Bases Administrativas y Bases Técnicas.",
      "Verificar existencia de un acto que apruebe las Bases."
    ]
  },
  {
    "id": 2,
    "code": "H-02",
    "name": "Bases Técnicas describen claramente el bien o servicio",
    "desc": "Verificar que las Bases Técnicas describan con parámetros verificables el objeto de la licitación.",
    "where_to_look": "Bases Técnicas",
    "severity": "Muy Alto",
    "subtasks": [
      "Confirmar presencia de sección técnica explícita.",
      "Verificar cantidades, estándares, desempeño, etc."
    ]
  },
  {
    "id": 3,
    "code": "H-03",
    "name": "Bases Administrativas regulan etapas, plazos y criterios",
    "desc": "Verificar que las Bases incluyan etapas del proceso, plazos, consultas, criterios y adjudicación.",
    "where_to_look": "Bases Administrativas",
    "severity": "Alto",
    "subtasks": [
      "Verificar que cada criterio tenga definición, descripción y escala de puntaje.",
      "Verificar presencia de etapas: publicación, consultas, oferta, apertura, evaluación, adjudicación.",
      "Verificar presencia de fechas y horas límite.",
      "Verificar si las consultas son canalizadas a través del sistema o otros medios.",
      "Verificar que se adelanten cláusulas esenciales del contrato."
    ]
  },
  {
    "id": 4,
    "code": "H-07",
    "name": "Criterios técnicos y económicos claros con ponderaciones",
    "desc": "Verificar criterios con peso, fórmula y reglas de puntaje.",
    "where_to_look": "Bases Adm.",
    "severity": "Alto",
    "subtasks": [
      "Verificar que cada criterio tenga peso numérico.",
      "Verificar fórmulas/tabla.",
      "Verificar fórmula para asignar puntaje al precio."
    ]
  },
  {
    "id": 5,
    "code": "H-09",
    "name": "Ausencia de diferencias arbitrarias entre oferentes",
    "desc": "Detectar requisitos injustificados que favorezcan a alguien.",
    "where_to_look": "Bases Adm./Técnicas",
    "severity": "Alto",
    "subtasks": [
      "Verificar que ser local no sea requisito excluyente.\n",
      "Detectar marca o producto único sin equivalentes en el mercado. "
    ]
  },
  {
    "id": 6,
    "code": "H-13",
    "name": "Participación MIPYME no bloqueada",
    "desc": "Evaluar si requisitos bloquean a pequeñas empresas.",
    "where_to_look": "Bases Adm.",
    "severity": "Medio",
    "subtasks": [
      "Extraer patrimonio, facturación, etc.",
      "Comparar exigencias con monto del contrato."
    ]
  },
  {
    "id": 7,
    "code": "H-14",
    "name": "Existencia de criterio relacionado con integridad y compliance",
    "desc": "Verificar criterio sobre integridad/cumplimiento normativo.",
    "where_to_look": "Bases Adm.",
    "severity": "Medio",
    "subtasks": [
      "Verificar si el criterio está presente."
    ]
  },
  {
    "id": 8,
    "code": "H-31",
    "name": "Publicación del contrato y su aprobación",
    "desc": "Verificar publicación del contrato y su aprobación administrativa.",
    "where_to_look": "Ficha/Contrato",
    "severity": "Medio",
    "subtasks": [
      "Revisar que contrato esté anexado.",
      "Verificar publicación de resolución que aprueba el contrato."
    ]
  },
  {
    "id": 9,
    "code": "H-08",
    "name": "Criterios objetivos sin discrecionalidad excesiva",
    "desc": "Verificar ausencia de criterios ambiguos como 'a exclusivo juicio'.",
    "where_to_look": "Bases Adm.",
    "severity": "Bajo",
    "subtasks": [
      "Detectar 'a exclusivo criterio', 'si se estima conveniente', etc.",
      "Verificar reglas para empates."
    ]
  },
  {
    "id": 10,
    "code": "H-05",
    "name": "Presupuesto estimado declarado",
    "desc": "Verificar existencia de presupuesto referencial.",
    "where_to_look": "Ficha/Bases",
    "severity": "Bajo",
    "subtasks": [
      "Comparar montos de ficha y Bases."
    ]
  },
  {
    "id": 11,
    "code": "H-06",
    "name": "Bases orientadas a combinación ventajosa de costo-beneficio",
    "desc": "Verificar que no se use solo precio.",
    "where_to_look": "Bases Adm.",
    "severity": "Medio",
    "subtasks": [
      "Verificar que ponderaciones no privilegien precio casi 100%."
    ]
  }
]