import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from emporio.agent import AgentRunner
from emporio.catalog import Catalog
from emporio.config import Settings
from emporio.observability import Observability
from emporio.retrieval import PolicyIndex
from emporio.sessions import SessionStore
from emporio.tools import make_tools

logger = logging.getLogger(__name__)

PROVIDER_ERROR_MESSAGES = {
    "provider_auth_error": "Não foi possível autenticar no provedor. Confira a chave configurada.",
    "provider_credit_error": (
        "O provedor não autorizou o uso do saldo. Confira créditos e limites da chave."
    ),
    "provider_request_error": "O provedor não aceitou o modelo ou os parâmetros da requisição.",
    "provider_rate_limit": "O provedor limitou as requisições. Aguarde e tente novamente.",
    "provider_timeout": "O provedor ultrapassou o tempo limite. Tente novamente.",
}


class AgentUnavailable(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error"):
        super().__init__(message)
        self.code = code


def _provider_failure(exc: Exception) -> AgentUnavailable:
    """Classificação por status, adaptada do case Yaitec; nunca repassa o corpo do provedor."""
    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        code = "provider_auth_error"
    elif status == 402:
        code = "provider_credit_error"
    elif status in {400, 404}:
        code = "provider_request_error"
    elif status == 429:
        code = "provider_rate_limit"
    elif isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        code = "provider_timeout"
    else:
        code = "provider_error"
    return AgentUnavailable(
        PROVIDER_ERROR_MESSAGES.get(
            code,
            "Não foi possível consultar o assistente agora. "
            "Tente novamente em instantes ou fale com a equipe.",
        ),
        code=code,
    )


class VerificationFailed(ValueError):
    pass


class VerificationRateLimited(RuntimeError):
    pass


class ChatService:
    def __init__(self, settings: Settings, model=None):
        self.settings = settings
        self.catalog = Catalog(settings.data_dir, settings.state_dir / "catalog.sqlite3")
        self.policies = PolicyIndex(settings.data_dir / "politicas_da_loja.pdf")
        self.sessions = SessionStore(settings.state_dir / "sessions.sqlite3")
        self.observability = Observability(settings)
        self.model = model
        if model is None and settings.provider == "openai":
            from langchain_openai import ChatOpenAI

            self.model = ChatOpenAI(
                model=settings.model,
                api_key=settings.openai_api_key.get_secret_value(),
                temperature=0.2,
                timeout=settings.llm_timeout,
                max_retries=1,
                max_tokens=1600,
            )
        elif model is None and settings.provider == "openrouter":
            from langchain_openrouter import ChatOpenRouter

            self.model = ChatOpenRouter(
                model=settings.model,
                api_key=settings.openrouter_api_key.get_secret_value(),
                base_url=settings.openrouter_base_url,
                app_url=settings.openrouter_site_url,
                app_title="Emporio da Musica - Artefact",
                temperature=0.2,
                max_tokens=1600,
                # O SDK nativo usa milissegundos, diferente do ChatOpenAI.
                timeout=max(1, int(settings.llm_timeout * 1000)),
                max_retries=0,
                # Sem override, o SDK adota backoff de até uma hora mesmo com max_retries=0.
                model_kwargs={"retries": None},
                openrouter_provider={
                    "require_parameters": True,
                    "allow_fallbacks": False,
                    **(
                        {"order": settings.openrouter_provider_order}
                        if settings.openrouter_provider_order
                        else {}
                    ),
                },
            )
        elif model is None and settings.provider == "ollama":
            from langchain_ollama import ChatOllama

            self.model = ChatOllama(
                model=settings.model,
                base_url=settings.ollama_url,
                temperature=0.2,
                num_predict=1600,
                reasoning=False,
                client_kwargs={"timeout": settings.llm_timeout},
            )

    def create_session(self) -> dict:
        return self.sessions.create()

    def close(self):
        self.observability.close()

    def health(self) -> dict:
        counts = self.catalog.counts()
        return {
            "status": "ok",
            "provider": self.settings.provider,
            "model": self.settings.model,
            "counts": {
                "products": counts["products"],
                "orders": counts["orders"],
                "policy_chunks": len(self.policies.chunks),
            },
        }

    def verify_order(self, session_id: str, order_id: int, email: str) -> dict:
        self.sessions.context(session_id)
        if not self.sessions.allow_verification(session_id):
            raise VerificationRateLimited(
                "Muitas tentativas. Aguarde um minuto antes de tentar novamente."
            )
        if not self.catalog.verify_order(order_id, email):
            raise VerificationFailed("Não foi possível validar o pedido com os dados informados.")
        self.sessions.grant_order(session_id, order_id)
        return {"verified": True, "order_id": order_id}

    def chat(self, session_id: str, message: str) -> dict:
        message = message.strip()
        if not 1 <= len(message) <= 4000:
            raise ValueError("A mensagem deve conter de 1 a 4000 caracteres.")
        start = time.perf_counter()
        lease = (self.settings.max_tool_rounds + 2) * (self.settings.llm_timeout * 2 + 1) + 30
        with self.sessions.turn(session_id, lease_seconds=lease):
            context = self.sessions.context(session_id)
            history = self.sessions.history(session_id, limit=self.settings.history_turns * 2)
            today = datetime.now(ZoneInfo(self.settings.timezone)).date()
            model = self.model
            if model is None:
                from emporio.demo import DemoModel

                model = DemoModel(context, today)
            tools = make_tools(
                self.catalog, self.policies, self.sessions, session_id, message, today
            )
            try:
                result = AgentRunner(model, tools, self.settings.max_tool_rounds).run(
                    message,
                    history,
                    context,
                    today.isoformat(),
                    config=self.observability.config(session_id),
                )
            except Exception as exc:
                failure = _provider_failure(exc)
                logger.warning(
                    "agent_failure provider=%s type=%s code=%s",
                    self.settings.provider,
                    type(exc).__name__,
                    failure.code,
                )
                raise failure from None
            result.update(
                provider=self.settings.provider,
                model=self.settings.model,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            self.sessions.save_turn(session_id, message, result, result["context"])
        return result
