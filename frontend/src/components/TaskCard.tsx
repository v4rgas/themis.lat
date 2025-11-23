import "./TaskCard.css";
import { TASKS_MAP } from "../pages/tasksMap";
interface TaskEvent {
  type: "log" | "result" | "error";
  message: string;
  timestamp: string;
}

interface TaskResult {
  task_id: number;
  task_code: string;
  task_name: string;
  validation_passed: boolean;
  findings_count: number;
  investigation_summary?: string;
}

interface TaskCardProps {
  taskCode: string;
  taskId: number;
  taskName: string;
  severity: string;
  events: TaskEvent[];
  result?: TaskResult;
  status: "pending" | "in_progress" | "completed" | "failed";
}

export function TaskCard({
  taskId,
  severity,
  events,
  result,
  status,
  taskCode,
}: TaskCardProps) {
  const taskFromMap = TASKS_MAP.find((t) => t.code === taskCode)!;
  const displayName = taskFromMap.name;
  const displayDesc = taskFromMap.desc;

  const hasValidationFailedMessage = events.some((event) =>
    event.message.includes(
      "Unknown title investigation complete. Validation passed: False"
    )
  );

  const hasValidationPassedMessage = events.some((event) =>
    event.message.includes(
      "Unknown title investigation complete. Validation passed: True"
    )
  );

  const getStatusColor = () => {
    switch (status) {
      case "pending":
        return "#2388aa";
      case "in_progress":
        return "#38b9d9";
      case "completed":
        return "#27ae60";
      case "failed":
        return "#e74c3c";
      default:
        return "#2388aa";
    }
  };

  const getStatusText = () => {
    if (hasValidationPassedMessage && status === "in_progress") {
      return "✓";
    }
    if (hasValidationFailedMessage && status === "in_progress") {
      return "✗";
    }
    switch (status) {
      case "pending":
        return "Pendiente";
      case "in_progress":
        return "En Progreso";
      case "completed":
        return "Completado";
      case "failed":
        return "Fallido";
      default:
        return "Desconocido";
    }
  };

  const getSeverityColor = () => {
    switch (severity) {
      case "Crítico":
      case "Muy Alto":
        return "#e74c3c";
      case "Alto":
        return "#e67e22";
      case "Medio":
        return "#f39c12";
      case "Bajo":
        return "#27ae60";
      default:
        return "var(--text-secondary)";
    }
  };

  const isCompleted = status === "completed" || status === "failed";

  return (
    <div
      className={`task-card ${
        hasValidationPassedMessage ? "task-card-green" : ""
      } ${hasValidationFailedMessage ? "task-card-mint" : ""} ${
        isCompleted ? "task-card-completed" : ""
      }`}
    >
      <div className="task-card-header">
        <div className="task-card-title">
          <span className="task-code">{displayName}</span>
        </div>
        <div className="task-card-status" style={{ color: getStatusColor() }}>
          {(hasValidationPassedMessage || hasValidationFailedMessage) &&
          status === "in_progress" ? (
            <span className="status-checkmark">
              {hasValidationPassedMessage ? "✓" : "✗"}
            </span>
          ) : (
            <>
              <span
                className="status-dot"
                style={{ backgroundColor: getStatusColor() }}
              ></span>
              {getStatusText()}
            </>
          )}
        </div>
      </div>

      <div className="task-card-name">{displayDesc}</div>

      {events.length > 0 && (
        <div className="task-card-events">
          <div className="task-card-events-header">
            Eventos ({events.length})
          </div>
          <div className="task-card-events-list">
            {events
              .slice()
              .sort(
                (a, b) =>
                  new Date(b.timestamp).getTime() -
                  new Date(a.timestamp).getTime()
              )
              .slice(0, 3)
              .map((event, index) => (
                <div
                  key={index}
                  className={`task-event task-event-${event.type}`}
                  style={{ opacity: 1 - index * 0.3 }}
                >
                  <span className="task-event-time">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="task-event-message">{event.message}</span>
                </div>
              ))}
          </div>
        </div>
      )}
      {severity === "Unknown" ? null : (
        <span className="task-severity" style={{ color: getSeverityColor() }}>
          Severity: {severity}
        </span>
      )}

      {result && (
        <div className="task-card-result">
          <div
            className={`task-result-status ${
              result.validation_passed ? "passed" : "failed"
            }`}
          >
            {result.validation_passed ? "✓ APROBADO" : "✗ FALLADO"}
          </div>
          <div className="task-result-findings">
            Hallazgos: {result.findings_count}
          </div>
          {result.investigation_summary && (
            <div className="task-result-summary">
              {result.investigation_summary}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
