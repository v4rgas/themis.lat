"""
WebSocket Streaming Middleware for Fraud Detection Agents

This middleware sends real-time events to the frontend via WebSocket
when agents are executing, including:
- Before calling the LLM
- Before/after executing tools
"""

import asyncio
import threading
from datetime import datetime
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

from app.utils.websocket_manager import manager


def send_ws_event_sync(session_id: str, event: dict):
    """
    Helper function to send WebSocket events synchronously from sync context.
    Creates a new event loop in a thread if needed.
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a new thread to send the event
            def send_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(manager.send_observation(session_id, event))
                new_loop.close()

            thread = threading.Thread(target=send_in_thread)
            thread.start()
        else:
            # If no loop is running, we can use run_until_complete
            loop.run_until_complete(manager.send_observation(session_id, event))
    except RuntimeError:
        # No event loop, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.send_observation(session_id, event))
        loop.close()


class WebSocketStreamingMiddleware(AgentMiddleware):
    """
    Middleware that streams agent execution events to the frontend via WebSocket.

    This middleware implements two hooks:
    1. before_model: Fired before each LLM call
    2. wrap_tool_call: Wraps each tool execution

    Events are sent to the WebSocket session specified in the agent state.
    """

    def __init__(self):
        super().__init__()
        print("[MIDDLEWARE] WebSocketStreamingMiddleware initialized")

    # Mapeo de nombres de tools a mensajes user-friendly en español
    TOOL_MESSAGES = {
        "read_buyer_attachments_table": "Consultando documentos del tender...",
        "read_buyer_attachment_doc": "Leyendo contenido del documento...",
        "read_award_result": "Verificando resultado de adjudicación...",
        "read_award_result_attachment_doc": "Analizando documentos de adjudicación...",
        "get_plan": "Generando plan de investigación...",
        "test_tool": "Ejecutando test tool...",
        "another_tool": "Ejecutando another tool...",
    }

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Hook ejecutado ANTES de cada llamada al LLM.

        Envía un evento al frontend indicando que el agente está analizando con IA.

        Args:
            state: Estado del agente (incluye session_id y task_info)
            runtime: Runtime de LangGraph

        Returns:
            None (no modifica el state)
        """
        print(f"[MIDDLEWARE] before_model called! State keys: {list(state.keys())}")
        session_id = state.get("session_id")
        task_info = state.get("task_info", {})
        print(f"[MIDDLEWARE] session_id: {session_id}, task_info: {task_info}")

        if session_id:
            try:
                task_name = task_info.get("name", "investigación")
                task_id = task_info.get("id", "")
                task_prefix = f"[TASK {task_id}] " if task_id else ""
                message = f"{task_prefix}Analizando con IA: {task_name}..."

                # Enviar evento por websocket
                send_ws_event_sync(
                    session_id,
                    {
                        "type": "log",
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print(f"[MIDDLEWARE] Sent log event: {message}")
            except Exception as e:
                print(f"[MIDDLEWARE] Error sending before_model event: {e}")
                import traceback
                traceback.print_exc()

        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """
        Hook que envuelve CADA ejecución de tool.

        Se ejecuta ANTES y DESPUÉS de invocar el tool.
        Envía un evento al frontend indicando qué tool se está ejecutando.

        Args:
            request: Request del tool con información del tool_call y state
            handler: Función que ejecuta el tool

        Returns:
            El resultado del tool (ToolMessage o Command)
        """
        session_id = request.state.get("session_id")
        tool_name = request.tool_call["name"]

        # ANTES de ejecutar el tool
        if session_id:
            try:
                # Obtener task_info del state
                task_info = request.state.get("task_info", {})
                task_id = task_info.get("id", "")
                task_prefix = f"[TASK {task_id}] " if task_id else ""

                # Obtener mensaje user-friendly para el tool
                base_message = self.TOOL_MESSAGES.get(
                    tool_name, f"Ejecutando {tool_name}..."
                )
                message = f"{task_prefix}{base_message}"

                # Enviar evento por websocket
                send_ws_event_sync(
                    session_id,
                    {
                        "type": "log",
                        "message": message,
                        "tool": tool_name,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print(f"[MIDDLEWARE] Sent log event: {message} ({tool_name})")
            except Exception as e:
                print(f"[MIDDLEWARE] Error sending tool event: {e}")
                import traceback
                traceback.print_exc()

        # Ejecutar el tool
        result = handler(request)

        # DESPUÉS de ejecutar el tool
        # Aquí podríamos agregar lógica adicional si necesitamos
        # (por ejemplo, enviar un evento de "tool completed")

        return result
