import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, useRef } from "react";
import "./Detail.css";
import { endpoints } from "../config/api";
import { TaskCard } from "../components/TaskCard";

interface LogEvent {
  type: "log" | "result" | "error";
  message: string;
  timestamp: string;
  task_code?: string;
  tasks_by_id?: any[];
  workflow_summary?: string;
  status?: string;
}

interface TaskInfo {
  code: string;
  id: number;
  name: string;
  severity: string;
  events: LogEvent[];
  result?: {
    task_id: number;
    task_code: string;
    task_name: string;
    validation_passed: boolean;
    findings_count: number;
    investigation_summary?: string;
  };
  status: "pending" | "in_progress" | "completed" | "failed";
}

export function Detail() {
  const location = useLocation();
  const navigate = useNavigate();
  const [nodeData, setNodeData] = useState<any>(null);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [tasks, setTasks] = useState<Map<string, TaskInfo>>(new Map());
  const [isInvestigating, setIsInvestigating] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const latestLogRef = useRef<HTMLDivElement | null>(null);
  const timelineContainerRef = useRef<HTMLDivElement | null>(null);
  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (location.state?.nodeData) {
      setNodeData(location.state.nodeData);
    } else {
      navigate("/explore");
    }
  }, [location, navigate]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    if (
      logs.length > 0 &&
      timelineContainerRef.current &&
      latestLogRef.current
    ) {
      const container = timelineContainerRef.current;
      const logElement = latestLogRef.current;
      const containerRect = container.getBoundingClientRect();
      const logRect = logElement.getBoundingClientRect();
      const scrollTop =
        container.scrollTop +
        (logRect.top - containerRect.top) -
        container.clientHeight / 2 +
        logElement.clientHeight / 2;
      container.scrollTo({
        top: Math.max(0, scrollTop),
        behavior: "smooth",
      });
    }
  }, [logs]);

  const connectWebSocket = (sessionId: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(endpoints.ws(sessionId));

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      const log: LogEvent = JSON.parse(event.data);
      console.log("Received log:", log);

      setLogs((prev) => [...prev, log]);

      // Handle task-related events
      if (log.task_code) {
        setTasks((prevTasks) => {
          const newTasks = new Map(prevTasks);
          const taskCode = log.task_code!;

          // Get or create task entry
          let taskInfo = newTasks.get(taskCode);
          if (!taskInfo) {
            // Create new task entry - we'll get name and severity from result events
            taskInfo = {
              code: taskCode,
              id: 0, // Will be updated from result
              name: `Task ${taskCode}`, // Will be updated from result
              severity: "Unknown", // Will be updated from result
              events: [],
              status: "pending",
            };
            newTasks.set(taskCode, taskInfo);
          }

          // Add event to task
          taskInfo.events = [...taskInfo.events, log];

          // Check for completion message
          if (
            log.message.includes(
              "Unknown title investigation complete. Validation passed: True"
            )
          ) {
            taskInfo.status = "completed";
          } else if (
            log.message.includes(
              "Unknown title investigation complete. Validation passed: False"
            )
          ) {
            taskInfo.status = "failed";
          } else {
            // Update status based on event type
            if (log.type === "log") {
              if (taskInfo.status === "pending") {
                taskInfo.status = "in_progress";
              }
            } else if (log.type === "result") {
              taskInfo.status = "completed";
            } else if (log.type === "error") {
              taskInfo.status = "failed";
            }
          }

          return newTasks;
        });
      }

      // Handle result events with tasks_by_id to update task results
      if (log.type === "result" && log.tasks_by_id) {
        setTasks((prevTasks) => {
          const newTasks = new Map(prevTasks);

          log.tasks_by_id!.forEach((taskResult: any) => {
            const taskCode = taskResult.task_code;
            const taskInfo = newTasks.get(taskCode);


            if (taskInfo) {
              taskInfo.id = taskResult.task_id;
              taskInfo.name = taskResult.task_name;
              taskInfo.result = {
                task_id: taskResult.task_id,
                task_code: taskResult.task_code,
                task_name: taskResult.task_name,
                validation_passed: taskResult.validation_passed,
                findings_count: taskResult.findings_count,
                investigation_summary: taskResult.investigation_summary,
              };
              taskInfo.status = taskResult.validation_passed
                ? "completed"
                : "failed";
            } else {
              // Create task entry from result if it doesn't exist
              newTasks.set(taskCode, {
                code: taskCode,
                id: taskResult.task_id,
                name: taskResult.task_name,
                severity: "Unknown", // Not available in result
                events: [],
                result: {
                  task_id: taskResult.task_id,
                  task_code: taskResult.task_code,
                  task_name: taskResult.task_name,
                  validation_passed: taskResult.validation_passed,
                  findings_count: taskResult.findings_count,
                  investigation_summary: taskResult.investigation_summary,
                },
                status: taskResult.validation_passed ? "completed" : "failed",
              });
            }
          });

          return newTasks;
        });
      }

      // If we receive a result or error, stop investigating
      if (log.type === "result" || log.type === "error") {
        setIsInvestigating(false);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
    };

    wsRef.current = ws;
  };

  const startInvestigation = async () => {
    setIsInvestigating(true);
    setLogs([]);
    setTasks(new Map());

    try {
      const response = await fetch(endpoints.investigate, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tender_id: nodeData.CodigoExterno,
        }),
      });

      const data = await response.json();
      connectWebSocket(data.session_id);
    } catch (error) {
      console.error("Error starting investigation:", error);
      setIsInvestigating(false);
    }
  };

  if (!nodeData) {
    return (
      <div className="detail-container">
        <div className="loader"></div>
      </div>
    );
  }

  const hasStartedInvestigation = tasks.size > 0 || logs.length > 0;

  if (!hasStartedInvestigation) {
    return (
      <div className="detail-container">
        <Summary
          nodeData={nodeData}
          isInvestigating={isInvestigating}
          logs={logs}
          startInvestigation={startInvestigation}
        />
      </div>
    );
  }

  return (
    <div className="detail-container">
      <div className="investigation-controls">
        <button
          onClick={() => navigate("/explore")}
          className="back-button-corner"
        >
          ← Explorar
        </button>
        <button
          className="details-dialog-trigger"
          onClick={() => dialogRef.current?.showModal()}
        >
          Ver Detalles
        </button>
        <dialog
          ref={dialogRef}
          className="dialog-content"
          onClick={(e) => {
            if (e.target === dialogRef.current) {
              dialogRef.current?.close();
            }
          }}
        >
          <div className="dialog-inner" onClick={(e) => e.stopPropagation()}>
            <h2 className="dialog-title">
              {nodeData.tender_name || nodeData.CodigoExterno}
            </h2>
            <TenderDetails nodeData={nodeData} />
            <button
              className="dialog-close"
              onClick={() => dialogRef.current?.close()}
            >
              ✕
            </button>
          </div>
        </dialog>
      </div>

      <div className="investigation-layout">
        {tasks.size > 0 && (
          <div className="tasks-section">
            <h2 className="tasks-section-title">Tareas de Investigación</h2>
            <div className="tasks-grid">
              {Array.from(tasks.values())
                .sort((a, b) => {
                  const aCompleted =
                    a.status === "completed" || a.status === "failed";
                  const bCompleted =
                    b.status === "completed" || b.status === "failed";
                  if (aCompleted && !bCompleted) return -1;
                  if (!aCompleted && bCompleted) return 1;
                  return a.code.localeCompare(b.code);
                })
                .map((task) => (
                  <TaskCard
                    key={`${task.code}-${task.status}`}
                    taskCode={task.code}
                    taskId={task.id}
                    taskName={task.name}
                    severity={task.severity}
                    events={task.events}
                    result={task.result}
                    status={task.status}
                  />
                ))}
            </div>
          </div>
        )}

        {logs.length > 0 && (
          <div
            className={`console-wrapper ${
              tasks.size > 0 ? "with-tasks" : "full-width"
            }`}
          >
            <div className="console-header">
              <div
                className={`console-title ${isInvestigating ? "pulsing" : ""}`}
              >
                <span className="console-icon">▸</span>
                <span className={isInvestigating ? "wave-text" : ""}>
                  Investigación en Progreso
                </span>
                {!isInvestigating && (
                  <span className="console-status">● Completada</span>
                )}
              </div>
              <div className="console-info">{logs.length} eventos</div>
            </div>
            <div className="timeline-container" ref={timelineContainerRef}>
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
                          {log.type === "log"
                            ? ""
                            : log.type === "result"
                            ? "[RESULT]"
                            : "[ERROR]"}
                        </span>
                        <span className="node-message">{log.message}</span>
                      </div>

                      {log.type === "result" && log.tasks_by_id && (
                        <div className="result-details">
                          <h3>Resultados de Tareas</h3>
                          {log.tasks_by_id.map((task, idx) => (
                            <div
                              key={idx}
                              className={`task-result ${
                                task.validation_passed ? "passed" : "failed"
                              }`}
                            >
                              <div className="task-header">
                                <span className="task-code">
                                  {task.task_code}
                                </span>
                                <span
                                  className={`task-status ${
                                    task.validation_passed ? "passed" : "failed"
                                  }`}
                                >
                                  {task.validation_passed
                                    ? "✓ APROBADO"
                                    : "✗ FALLADO"}
                                </span>
                              </div>
                              <div className="task-name">{task.task_name}</div>
                              <div className="task-findings">
                                Hallazgos: {task.findings_count}
                              </div>
                            </div>
                          ))}
                          {log.workflow_summary && (
                            <pre className="workflow-summary">
                              {log.workflow_summary}
                            </pre>
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
    </div>
  );
}

function Summary({
  nodeData,
  isInvestigating,
  logs,
  startInvestigation,
}: {
  nodeData: any;
  isInvestigating: boolean;
  logs: LogEvent[];
  startInvestigation: () => void;
}) {
  const navigate = useNavigate();

  return (
    <div>
      <div className="detail-header">
        <button onClick={() => navigate("/explore")} className="back-button">
          ← Explorar
        </button>
        <h1 className="detail-title">
          {nodeData.tender_name || nodeData.CodigoExterno}
        </h1>
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
      <div className="summary-section">
        <div className="summary-row">
          <span className="summary-label">Proveedor</span>
          <span className="summary-value">
            {nodeData.supplier_name || "N/A"}
          </span>
        </div>
        {nodeData.supplier_rut && (
          <div className="summary-row">
            <span className="summary-label">RUT</span>
            <span className="summary-value">
              {nodeData.supplier_rut
                .toString()
                .replace(/\B(?=(\d{3})+(?!\d))/g, ".")}
            </span>
          </div>
        )}
        <div className="summary-row">
          <span className="summary-label">Monto Adjudicado</span>
          <span className="summary-value highlight">
            {nodeData.MontoLineaAdjudica
              ? `$${nodeData.MontoLineaAdjudica.toLocaleString("es-CL", {
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                })}`
              : "N/A"}
          </span>
        </div>
        {nodeData.MontoEstimado && (
          <div className="summary-row">
            <span className="summary-label">Monto Estimado</span>
            <span className="summary-value">
              $
              {nodeData.MontoEstimado.toLocaleString("es-CL", {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              })}
            </span>
          </div>
        )}
        {nodeData.FechaAdjudicacion &&
          new Date(nodeData.FechaAdjudicacion).getFullYear() >= 2000 && (
            <div className="summary-row">
              <span className="summary-label">Fecha Adjudicación</span>
              <span className="summary-value">
                {new Date(nodeData.FechaAdjudicacion).toLocaleDateString(
                  "es-ES",
                  { year: "numeric", month: "long", day: "numeric" }
                )}
              </span>
            </div>
          )}
        {nodeData.FechaPublicacion &&
          new Date(nodeData.FechaPublicacion).getFullYear() >= 2000 && (
            <div className="summary-row">
              <span className="summary-label">Fecha Publicación</span>
              <span className="summary-value">
                {new Date(nodeData.FechaPublicacion).toLocaleDateString(
                  "es-ES",
                  { year: "numeric", month: "long", day: "numeric" }
                )}
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
            <span className="summary-value warning">
              {nodeData.CantidadReclamos}
            </span>
          </div>
        )}
      </div>

      {!isInvestigating && logs.length === 0 && (
        <div className="investigation-start">
          <button onClick={startInvestigation} className="start-button">
            Iniciar Investigación
          </button>
        </div>
      )}
    </div>
  );
}

function TenderDetails({ nodeData }: { nodeData: any }) {
  const formatValue = (key: string, value: any) => {
    if (value === null || value === undefined) return "N/A";

    const moneyFields = [
      "Monto Estimado Adjudicado",
      "MontoEstimado",
      "MontoLineaAdjudica",
      "MontoUnitarioOferta",
      "Valor Total Ofertado",
    ];
    const integerFields = [
      "Cantidad",
      "Cantidad Ofertada",
      "CantidadAdjudicada",
      "CantidadReclamos",
      "NumeroAprobacion",
      "NumeroOferentes",
    ];
    const codeFields = [
      "CodigoEstadoLicitacion",
      "CodigoOrganismo",
      "CodigoProveedor",
      "CodigoTipo",
      "CodigoExterno",
    ];

    if (key === "supplier_rut") {
      return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    } else if (moneyFields.includes(key)) {
      const numValue = typeof value === "number" ? value : parseFloat(value);
      return !isNaN(numValue)
        ? "$" +
            numValue.toLocaleString("es-CL", {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            })
        : "N/A";
    } else if (integerFields.includes(key)) {
      const numValue = typeof value === "number" ? value : parseFloat(value);
      return !isNaN(numValue)
        ? Math.round(numValue).toLocaleString("es-CL")
        : "N/A";
    } else if (codeFields.includes(key)) {
      return value.toString();
    } else if (key === "x" || key === "y") {
      const numValue = typeof value === "number" ? value : parseFloat(value);
      return !isNaN(numValue)
        ? numValue.toLocaleString("es-CL", {
            minimumFractionDigits: 3,
            maximumFractionDigits: 3,
          })
        : "N/A";
    } else if (
      key.toLowerCase().includes("fecha") ||
      key.toLowerCase().includes("date")
    ) {
      const date = new Date(value);
      const isFirstActivityDate = key === "first_activity_date";
      if (
        !isNaN(date.getTime()) &&
        (isFirstActivityDate || date.getFullYear() >= 2000)
      ) {
        return date.toLocaleDateString("es-ES", {
          year: "numeric",
          month: "long",
          day: "numeric",
        });
      }
      return "N/A";
    } else if (typeof value === "number" && (value === 0 || value === 1)) {
      return value === 1 ? "Sí" : "No";
    } else if (typeof value === "number") {
      return value.toLocaleString("es-CL");
    }
    return value.toString();
  };

  const priorityFields = [
    "tender_name",
    "CodigoExterno",
    "supplier_name",
    "supplier_rut",
    "MontoLineaAdjudica",
    "MontoEstimado",
    "FechaAdjudicacion",
    "FechaPublicacion",
    "NumeroOferentes",
    "CantidadReclamos",
  ];

  const allFields = Object.keys(nodeData).filter((key) => !key.startsWith("_"));
  const orderedFields = [
    ...priorityFields.filter((key) => allFields.includes(key)),
    ...allFields.filter((key) => !priorityFields.includes(key)),
  ];

  return (
    <div className="details-panel">
      {orderedFields.map((key) => (
        <div key={key} className="detail-item">
          <span className="detail-key">{key}</span>
          <span className="detail-value">
            {formatValue(key, nodeData[key])}
          </span>
        </div>
      ))}
    </div>
  );
}
