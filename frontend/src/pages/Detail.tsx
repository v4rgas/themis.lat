import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import './Detail.css'
import { endpoints } from '../config/api'

interface LogEvent {
  type: 'log' | 'result' | 'error'
  message: string
  timestamp: string
  tasks_by_id?: any[]
  workflow_summary?: string
  status?: string
}

export function Detail() {
  const location = useLocation()
  const navigate = useNavigate()
  const [nodeData, setNodeData] = useState<any>(null)
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [isInvestigating, setIsInvestigating] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const latestLogRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (location.state?.nodeData) {
      setNodeData(location.state.nodeData)
    } else {
      navigate('/explore')
    }
  }, [location, navigate])

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  useEffect(() => {
    if (logs.length > 0) {
      latestLogRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [logs])

  const connectWebSocket = (sessionId: string) => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const ws = new WebSocket(endpoints.ws(sessionId))

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      const log: LogEvent = JSON.parse(event.data)
      console.log('Received log:', log)

      setLogs((prev) => [...prev, log])

      // If we receive a result or error, stop investigating
      if (log.type === 'result' || log.type === 'error') {
        setIsInvestigating(false)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
    }

    wsRef.current = ws
  }

  const startInvestigation = async () => {
    setIsInvestigating(true)
    setLogs([])

    try {
      const response = await fetch(endpoints.investigate, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tender_id: nodeData.CodigoExterno,
        }),
      })

      const data = await response.json()
      connectWebSocket(data.session_id)
    } catch (error) {
      console.error('Error starting investigation:', error)
      setIsInvestigating(false)
    }
  }

  if (!nodeData) {
    return (
      <div className="detail-container">
        <div className="loader"></div>
      </div>
    )
  }

  return (
    <div className="detail-container">
      <div className="detail-header">
        <button onClick={() => navigate('/explore')} className="back-button">
          ← Explorar
        </button>
        <h1 className="detail-title">{nodeData.tender_name || nodeData.CodigoExterno}</h1>
        {nodeData.CodigoExterno && (
          <div>
            <p className="detail-code">{nodeData.CodigoExterno}</p>
            <a
              href={`https://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion=${nodeData.CodigoExterno}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mercado-link"
            >
              Ver en Mercado Público →
            </a>
          </div>
        )}
      </div>

      {/* Summary Section */}
      <div className="summary-section">
        <div className="summary-row">
          <span className="summary-label">Proveedor</span>
          <span className="summary-value">{nodeData.supplier_name || 'N/A'}</span>
        </div>
        {nodeData.supplier_rut && (
          <div className="summary-row">
            <span className="summary-label">RUT</span>
            <span className="summary-value">{nodeData.supplier_rut.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.')}</span>
          </div>
        )}
        <div className="summary-row">
          <span className="summary-label">Monto Adjudicado</span>
          <span className="summary-value highlight">
            {nodeData.MontoLineaAdjudica
              ? `$${nodeData.MontoLineaAdjudica.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
              : 'N/A'}
          </span>
        </div>
        {nodeData.MontoEstimado && (
          <div className="summary-row">
            <span className="summary-label">Monto Estimado</span>
            <span className="summary-value">
              ${nodeData.MontoEstimado.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </span>
          </div>
        )}
        {nodeData.FechaAdjudicacion && new Date(nodeData.FechaAdjudicacion).getFullYear() >= 2000 && (
          <div className="summary-row">
            <span className="summary-label">Fecha Adjudicación</span>
            <span className="summary-value">
              {new Date(nodeData.FechaAdjudicacion).toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })}
            </span>
          </div>
        )}
        {nodeData.FechaPublicacion && new Date(nodeData.FechaPublicacion).getFullYear() >= 2000 && (
          <div className="summary-row">
            <span className="summary-label">Fecha Publicación</span>
            <span className="summary-value">
              {new Date(nodeData.FechaPublicacion).toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })}
            </span>
          </div>
        )}
        {nodeData.NumeroOferentes && (
          <div className="summary-row">
            <span className="summary-label">Oferentes</span>
            <span className="summary-value">{nodeData.NumeroOferentes}</span>
          </div>
        )}
        {nodeData.CantidadReclamos > 0 && (
          <div className="summary-row">
            <span className="summary-label">Reclamos</span>
            <span className="summary-value warning">{nodeData.CantidadReclamos}</span>
          </div>
        )}
      </div>

      <button
        onClick={() => setShowDetails(!showDetails)}
        className="toggle-details"
      >
        {showDetails ? 'Ocultar detalles completos' : 'Ver detalles completos'}
      </button>

      {showDetails && (
        <div className="details-panel">
          {(() => {
            const formatValue = (key: string, value: any) => {
              if (value === null || value === undefined) return 'N/A'

              const moneyFields = ['Monto Estimado Adjudicado', 'MontoEstimado', 'MontoLineaAdjudica', 'MontoUnitarioOferta', 'Valor Total Ofertado']
              const integerFields = ['Cantidad', 'Cantidad Ofertada', 'CantidadAdjudicada', 'CantidadReclamos', 'NumeroAprobacion', 'NumeroOferentes']
              const codeFields = ['CodigoEstadoLicitacion', 'CodigoOrganismo', 'CodigoProveedor', 'CodigoTipo', 'CodigoExterno']

              if (key === 'supplier_rut') {
                return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.')
              } else if (moneyFields.includes(key)) {
                const numValue = typeof value === 'number' ? value : parseFloat(value)
                return !isNaN(numValue) ? '$' + numValue.toLocaleString('es-CL', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : 'N/A'
              } else if (integerFields.includes(key)) {
                const numValue = typeof value === 'number' ? value : parseFloat(value)
                return !isNaN(numValue) ? Math.round(numValue).toLocaleString('es-CL') : 'N/A'
              } else if (codeFields.includes(key)) {
                return value.toString()
              } else if (key === 'x' || key === 'y') {
                const numValue = typeof value === 'number' ? value : parseFloat(value)
                return !isNaN(numValue) ? numValue.toLocaleString('es-CL', { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : 'N/A'
              } else if (key.toLowerCase().includes('fecha') || key.toLowerCase().includes('date')) {
                const date = new Date(value)
                const isFirstActivityDate = key === 'first_activity_date'
                if (!isNaN(date.getTime()) && (isFirstActivityDate || date.getFullYear() >= 2000)) {
                  return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })
                }
                return 'N/A'
              } else if (typeof value === 'number' && (value === 0 || value === 1)) {
                return value === 1 ? 'Sí' : 'No'
              } else if (typeof value === 'number') {
                return value.toLocaleString('es-CL')
              }
              return value.toString()
            }

            // Organize fields by importance
            const priorityFields = [
              'tender_name', 'CodigoExterno', 'supplier_name', 'supplier_rut',
              'MontoLineaAdjudica', 'MontoEstimado', 'FechaAdjudicacion', 'FechaPublicacion',
              'NumeroOferentes', 'CantidadReclamos'
            ]

            const allFields = Object.keys(nodeData).filter(key => !key.startsWith('_'))
            const orderedFields = [
              ...priorityFields.filter(key => allFields.includes(key)),
              ...allFields.filter(key => !priorityFields.includes(key))
            ]

            return orderedFields.map((key) => (
              <div key={key} className="detail-item">
                <span className="detail-key">{key}</span>
                <span className="detail-value">{formatValue(key, nodeData[key])}</span>
              </div>
            ))
          })()}
        </div>
      )}

      {!isInvestigating && logs.length === 0 && (
        <div className="investigation-start">
          <button onClick={startInvestigation} className="start-button">
            Iniciar Investigación
          </button>
        </div>
      )}

      {logs.length > 0 && (
        <div className="console-wrapper">
          <div className="console-header">
            <div className="console-title">
              <span className="console-icon">▸</span>
              Investigación en Progreso
              {!isInvestigating && <span className="console-status">● Completada</span>}
            </div>
            <div className="console-info">{logs.length} eventos</div>
          </div>
          <div className="timeline-container">
            {logs.map((log, index) => (
              <div
                key={index}
                className="timeline-item"
                ref={index === logs.length - 1 ? latestLogRef : null}
              >
                <div className={`log-node ${log.type}`}>
                  <div className="node-content">
                    <div className="node-header">
                      <span className="node-timestamp">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="node-type">
                        {log.type === 'log' ? '[LOG]' : log.type === 'result' ? '[RESULT]' : '[ERROR]'}
                      </span>
                      <span className="node-message">{log.message}</span>
                    </div>

                    {log.type === 'result' && log.tasks_by_id && (
                      <div className="result-details">
                        <h3>Resultados de Tareas</h3>
                        {log.tasks_by_id.map((task, idx) => (
                          <div key={idx} className={`task-result ${task.validation_passed ? 'passed' : 'failed'}`}>
                            <div className="task-header">
                              <span className="task-code">{task.task_code}</span>
                              <span className={`task-status ${task.validation_passed ? 'passed' : 'failed'}`}>
                                {task.validation_passed ? '✓ APROBADO' : '✗ FALLADO'}
                              </span>
                            </div>
                            <div className="task-name">{task.task_name}</div>
                            <div className="task-findings">Hallazgos: {task.findings_count}</div>
                          </div>
                        ))}
                        {log.workflow_summary && (
                          <pre className="workflow-summary">{log.workflow_summary}</pre>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
