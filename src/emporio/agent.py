import json
import logging
import time
from operator import add
from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from emporio.grounding import supported_answer
from emporio.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    outputs: Annotated[list[dict], add]
    traces: Annotated[list[dict], add]
    rounds: int


class AgentRunner:
    def __init__(self, model, tools: list, max_rounds: int):
        self.model = model.bind_tools(tools)
        self.tools = {t.name: t for t in tools}
        self.max_rounds = max_rounds
        graph = StateGraph(AgentState)
        graph.add_node("model", self._model)
        graph.add_node("tools", self._tools)
        graph.add_node("limit", self._limit)
        graph.add_edge(START, "model")
        graph.add_conditional_edges(
            "model", self._next, {"tools": "tools", "done": END, "limit": "limit"}
        )
        graph.add_edge("tools", "model")
        graph.add_edge("limit", END)
        self.graph = graph.compile()

    def _model(self, state: AgentState) -> dict:
        response = self.model.invoke(state["messages"])
        if not isinstance(response, AIMessage):
            raise TypeError("O provedor não retornou uma mensagem de assistente válida.")
        if response.invalid_tool_calls or (not response.tool_calls and not response.text.strip()):
            raise ValueError("O provedor retornou uma chamada malformada ou resposta vazia.")
        return {"messages": [response.model_copy(update={"id": uuid4().hex})]}

    def _next(self, state: AgentState) -> str:
        if not state["messages"][-1].tool_calls:
            return "done"
        if len(state["messages"][-1].tool_calls) > 8:
            return "limit"
        return "limit" if state["rounds"] >= self.max_rounds else "tools"

    def _limit(self, state: AgentState) -> dict:
        return {
            "messages": [
                AIMessage(
                    content="Cheguei ao limite de consultas desta resposta. "
                    "Tente uma pergunta mais específica ou fale com a equipe."
                )
            ]
        }

    def _tools(self, state: AgentState) -> dict:
        messages, outputs, traces = [], [], []
        for call in state["messages"][-1].tool_calls[:8]:
            start = time.perf_counter()
            try:
                if call["name"] not in self.tools:
                    payload = {"error": "unknown_tool", "sources": []}
                else:
                    previous = next(
                        (
                            o
                            for o in state["outputs"] + outputs
                            if o["name"] == "create_support_ticket"
                        ),
                        None,
                    )
                    if call["name"] == "create_support_ticket" and previous:
                        payload = previous["result"]
                    else:
                        payload = self.tools[call["name"]].invoke(call["args"])
            except (ValidationError, ValueError, TypeError):
                payload = {
                    "error": "invalid_tool_arguments",
                    "sources": [],
                    "message": "Revise os argumentos da ferramenta.",
                }
            except Exception as exc:
                # Nunca registrar texto da mensagem, e-mail, token ou repr da exceção.
                logger.warning("tool_failure tool=%s type=%s", call["name"], type(exc).__name__)
                payload = {
                    "error": "tool_unavailable",
                    "sources": [],
                    "message": "Não foi possível consultar esta fonte agora.",
                }
            outputs.append({"name": call["name"], "args": call["args"], "result": payload})
            traces.append(
                {
                    "name": call["name"],
                    "ok": "error" not in payload,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
            messages.append(
                ToolMessage(
                    content=json.dumps(payload, ensure_ascii=False, default=str),
                    tool_call_id=call["id"],
                    name=call["name"],
                )
            )
        return {
            "messages": messages,
            "outputs": outputs,
            "traces": traces,
            "rounds": state["rounds"] + 1,
        }

    def run(
        self,
        question: str,
        history: list[dict],
        context: dict,
        today: str,
        *,
        config: dict | None = None,
    ) -> dict:
        system = (
            SYSTEM_PROMPT
            + f"\nData local da loja: {today}.\nContexto mínimo: "
            + json.dumps(context)
        )
        messages = [SystemMessage(content=system)]
        for entry in history:
            cls = HumanMessage if entry["role"] == "user" else AIMessage
            messages.append(cls(content=entry["content"]))
        messages.append(HumanMessage(content=question))
        state = self.graph.invoke(
            {"messages": messages, "outputs": [], "traces": [], "rounds": 0},
            config={**(config or {}), "recursion_limit": self.max_rounds * 2 + 5},
        )
        sources = {}
        new_context = context.copy()
        for output in state["outputs"]:
            payload = output["result"]
            if "error" in payload:
                continue
            for source in payload.get("sources", []):
                sources[source["id"]] = source
            if "products" in payload:
                new_context["products"] = [p["product_id"] for p in payload["products"]]
            elif "product" in payload:
                new_context["products"] = [payload["product"]["product_id"]]
            elif "quote" in payload:
                new_context["products"] = [payload["quote"]["product_id"]]
            if "assessment" in payload:
                new_context["return_request"] = output["args"]
                new_context["pending_return"] = (
                    payload["assessment"]["status"] == "needs_information"
                )
        answer = state["messages"][-1].text
        if not supported_answer(answer, state["outputs"]):
            answer = (
                "Preciso consultar uma fonte da loja para confirmar essa informação. "
                "Tente informar o modelo ou identificar o pedido para eu consultar."
            )
        return {
            "message": answer,
            "sources": list(sources.values()),
            "tools": state["traces"],
            "context": new_context,
        }
