import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import './Detail.css'

interface LogEvent {
  type: 'log'
  message: string
  timestamp: string
}

export function Detail() {
  const location = useLocation()
  const navigate = useNavigate()
  const [nodeData, setNodeData] = useState<any>(null)
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [isInvestigating, setIsInvestigating] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
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

    const ws = new WebSocket(`ws://localhost:8001/api/ws/${sessionId}`)

    ws.onopen = () => {
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      const log: LogEvent = JSON.parse(event.data)
      console.log('Received log:', log)

      setLogs((prev) => [...prev, log])
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
      const response = await fetch('http://localhost:8001/api/investigate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `Investigate tender ${nodeData.CodigoExterno || nodeData.tender_name}: Analyze for potential fraud or anomalies`,
        }),
      })

      const data = await response.json()
      setSessionId(data.session_id)

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
          <p className="detail-code">{nodeData.CodigoExterno}</p>
        )}

        <button
          onClick={() => setShowDetails(!showDetails)}
          className="toggle-details"
        >
          {showDetails ? 'Ocultar detalles' : 'Ver detalles'}
        </button>
      </div>

      {showDetails && (
        <div className="details-panel">
          {Object.keys(nodeData)
            .filter(key => !key.startsWith('_'))
            .map((key) => (
              <div key={key} className="detail-item">
                <span className="detail-key">{key.replace(/_/g, ' ')}</span>
                <span className="detail-value">
                  {nodeData[key]?.toString() || 'N/A'}
                </span>
              </div>
            ))}
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
        <div className="timeline-container">
          {logs.map((log, index) => (
            <div
              key={index}
              className="timeline-item"
              ref={index === logs.length - 1 ? latestLogRef : null}
            >
              {index > 0 && <div className="timeline-line" />}

              <div className="log-node">
                <div className="node-dot" />
                <div className="node-content">
                  <div className="node-header">
                    <span className="node-type">Log</span>
                    <span className="node-timestamp">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="node-message">{log.message}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
