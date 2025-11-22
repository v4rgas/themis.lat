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
    severity: str  # Critical, High, Medium, Low
    subtasks: List[str]  # List of subtask descriptions


INVESTIGATION_TASKS: List[InvestigationTask] = [
    {
        "id": 1,
        "code": "H-01",
        "name": "Existencia de Bases Administrativas y Bases Técnicas diferenciadas",
        "desc": "Verificar que existan documentos o secciones diferenciadas como Bases Administrativas y Bases Técnicas.",
        "where_to_look": "Anexos y contenido de Bases",
        "severity": "Crítico",
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
        "severity": "Alto",
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
        "severity": "Crítico",
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
        "code": "H-04-2",
        "name": "Extracción de monto",
        "desc": "Extraer monto para clasificación UTM o Monto directo dentro de la licitacion",
        "where_to_look": "Ficha/Bases",
        "severity": "Medio",
        "subtasks": []
    },
    {
        "id": 5,
        "code": "H-05",
        "name": "Presupuesto estimado declarado",
        "desc": "Verificar existencia de presupuesto referencial.",
        "where_to_look": "Ficha/Bases",
        "severity": "Alto",
        "subtasks": [
            "Comparar montos de ficha y Bases.",
            "Verificar si incluye impuestos y moneda."
        ]
    },
    {
        "id": 6,
        "code": "H-06",
        "name": "Bases orientadas a combinación ventajosa de costo-beneficio",
        "desc": "Verificar que no se use solo precio.",
        "where_to_look": "Bases Adm.",
        "severity": "Medio",
        "subtasks": [
            "Verificar que ponderaciones no privilegien precio casi 100%."
        ]
    },
    {
        "id": 7,
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
        "id": 8,
        "code": "H-08",
        "name": "Criterios objetivos sin discrecionalidad excesiva",
        "desc": "Verificar ausencia de criterios ambiguos como 'a exclusivo juicio'.",
        "where_to_look": "Bases Adm.",
        "severity": "Alto",
        "subtasks": [
            "Detectar 'a exclusivo criterio', 'si se estima conveniente', etc.",
            "Verificar reglas para empates."
        ]
    },
    {
        "id": 9,
        "code": "H-09",
        "name": "Ausencia de diferencias arbitrarias entre oferentes",
        "desc": "Detectar requisitos injustificados que favorezcan a alguien.",
        "where_to_look": "Bases Adm./Técnicas",
        "severity": "Crítico",
        "subtasks": [
            "Detectar domicilio/localidad como requisito excluyente.",
            "Evaluar proporcionalidad con rubro y monto.",
            "Detectar marca única sin equivalentes."
        ]
    },
    {
        "id": 10,
        "code": "H-10",
        "name": "Tratamiento de ofertas temerarias o riesgosas",
        "desc": "Verificar existencia de reglas para ofertas anormalmente bajas.",
        "where_to_look": "Bases/Informe",
        "severity": "Medio",
        "subtasks": [
            "Verificar criterios objetivos en Bases.",
            "Verificar si se pidió justificación al oferente.",
            "Verificar coherencia entre medidas y lo descrito en Bases."
        ]
    },
    {
        "id": 11,
        "code": "H-11",
        "name": "Servicios habituales deben incluir condiciones laborales",
        "desc": "Verificar evaluación de condiciones laborales cuando sea intensivo en personal.",
        "where_to_look": "Bases Adm.",
        "severity": "Crítico",
        "subtasks": [
            "Clasificar el tipo de servicio licitado.",
            "Verificar criterio sobre condiciones laborales.",
            "Verificar peso significativo del criterio."
        ]
    },
    {
        "id": 12,
        "code": "H-12",
        "name": "Preferencia local sin excluir a otros",
        "desc": "Verificar que ser local no sea requisito excluyente.",
        "where_to_look": "Bases Adm.",
        "severity": "Alto",
        "subtasks": [
            "Debe otorgar puntaje, no excluir.",
            "Verificar que el peso no desplace otros criterios.",
            "Detectar frases que excluyan indirectamente."
        ]
    },
    {
        "id": 13,
        "code": "H-13",
        "name": "Participación MIPYME no bloqueada",
        "desc": "Evaluar si requisitos bloquean a pequeñas empresas.",
        "where_to_look": "Bases Adm.",
        "severity": "Alto",
        "subtasks": [
            "Extraer patrimonio, facturación, etc.",
            "Comparar exigencias con monto del contrato.",
            "Comparar años/contratos requeridos."
        ]
    },
    {
        "id": 14,
        "code": "H-14",
        "name": "Existencia de criterio relacionado con integridad y compliance",
        "desc": "Verificar criterio sobre integridad/cumplimiento normativo.",
        "where_to_look": "Bases Adm.",
        "severity": "Alto",
        "subtasks": [
            "Verificar si el criterio está presente.",
            "Verificar que no sea simbólico."
        ]
    },
    {
        "id": 15,
        "code": "H-15",
        "name": "Cronograma completo descrito",
        "desc": "Verificar hitos mínimos del proceso.",
        "where_to_look": "Bases Adm.",
        "severity": "Bajo",
        "subtasks": [
            "Verificar ocho hitos clave.",
            "Validar orden secuencial.",
            "Detectar contradicciones de fechas."
        ]
    },
    {
        "id": 16,
        "code": "H-17",
        "name": "Publicación de modificaciones/aclaraciones",
        "desc": "Verificar que aclaraciones formen parte de Bases.",
        "where_to_look": "Ficha/Bases",
        "severity": "Crítico",
        "subtasks": [
            "Verificar documentos como 'Modificación de Bases'.",
            "Verificar que se indiquen como parte integral.",
            "Emitidas con tiempo razonable previo al cierre."
        ]
    },
    {
        "id": 17,
        "code": "H-18",
        "name": "Uso del Registro de Proveedores",
        "desc": "Verificar que el Registro se use para acreditar idoneidad.",
        "where_to_look": "Bases Adm.",
        "severity": "Bajo",
        "subtasks": [
            "Buscar referencia expresa."
        ]
    },
    {
        "id": 18,
        "code": "H-19",
        "name": "No exigencia de documentos redundantes",
        "desc": "Verificar que no pidan documentos ya listados en Registro.",
        "where_to_look": "Bases Adm.",
        "severity": "Bajo",
        "subtasks": [
            "Listar documentos exigidos.",
            "Marcar documentos duplicados."
        ]
    },
    {
        "id": 19,
        "code": "H-31",
        "name": "Publicación del contrato y su aprobación",
        "desc": "Verificar publicación del contrato y su aprobación administrativa.",
        "where_to_look": "Ficha/Contrato",
        "severity": "Alto",
        "subtasks": [
            "Revisar que contrato esté anexado.",
            "Verificar publicación de resolución que aprueba el contrato."
        ]
    }
]