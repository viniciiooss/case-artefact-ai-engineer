"""HTTP local para a Mel; capabilities de sessão ficam exclusivamente no backend."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from emporio.config import Settings
from emporio.service import (
    AgentUnavailable,
    ChatService,
    VerificationFailed,
    VerificationRateLimited,
)
from emporio.sessions import SessionBusy, SessionNotFound

WEB_DIR = Path(__file__).parent / "web"


class MessageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=4000)


class OrderAccessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    order_id: int = Field(gt=0)
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_app(settings: Settings | None = None, service: ChatService | None = None) -> FastAPI:
    """Construir a aplicação não lê dados nem abre bancos; o lifespan faz a carga."""

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.service = service or await run_in_threadpool(
            lambda: ChatService(settings or Settings())
        )
        try:
            yield
        finally:
            await run_in_threadpool(application.state.service.close)

    application = FastAPI(
        title="Empório da Música · Mel", lifespan=lifespan, docs_url=None, redoc_url=None
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(
                status_code=500,
                content={"detail": "Não foi possível concluir a solicitação. Tente novamente."},
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    def error_handler(status_code: int, message: str):
        async def handle(request: Request, exc: Exception):
            return JSONResponse(status_code=status_code, content={"detail": message})

        return handle

    for exception, code, message in [
        (SessionNotFound, 404, "Sessão não encontrada ou credencial inválida."),
        (SessionBusy, 409, "Uma resposta já está sendo preparada nesta conversa."),
        (
            AgentUnavailable,
            503,
            "O atendimento está indisponível agora. Tente novamente em instantes.",
        ),
        (VerificationFailed, 403, "Não foi possível identificar o pedido com esses dados."),
        (VerificationRateLimited, 429, "Muitas tentativas. Aguarde um minuto e tente novamente."),
    ]:
        application.add_exception_handler(exception, error_handler(code, message))
    application.add_exception_handler(
        RequestValidationError,
        error_handler(422, "Dados inválidos. Confira os campos e os limites informados."),
    )

    def get_service(request: Request) -> ChatService:
        return request.app.state.service

    Service = Annotated[ChatService, Depends(get_service)]

    def authenticate(
        session_id: str, service: Service, authorization: Annotated[str | None, Header()] = None
    ) -> str:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            raise HTTPException(
                401, "Credencial da conversa obrigatória.", headers={"WWW-Authenticate": "Bearer"}
            )
        service.sessions.authenticate(session_id, token.strip())
        return session_id

    Session = Annotated[str, Depends(authenticate)]

    @application.get("/api/health")
    def health(service: Service):
        return service.health()

    @application.post("/api/sessions", status_code=201)
    def create_session(service: Service):
        return service.create_session()

    @application.get("/api/sessions/{session_id}")
    def get_session(session_id: Session, service: Service):
        return {
            "session_id": session_id,
            "messages": service.sessions.history(session_id),
            "verified_orders": service.sessions.verified_orders(session_id),
        }

    @application.get("/api/sessions/{session_id}/history")
    def history(session_id: Session, service: Service):
        return service.sessions.history(session_id)

    @application.post("/api/sessions/{session_id}/messages")
    def message(session_id: Session, body: MessageInput, service: Service):
        return service.chat(session_id, body.message)

    @application.post("/api/sessions/{session_id}/order-access")
    def order_access(session_id: Session, body: OrderAccessInput, service: Service):
        return service.verify_order(session_id, body.order_id, body.email)

    @application.delete("/api/sessions/{session_id}", status_code=204)
    def delete_session(session_id: Session, service: Service):
        service.sessions.delete(session_id)
        return Response(status_code=204)

    @application.get("/api/products")
    def products(
        service: Service,
        query: Annotated[str, Query(max_length=200)] = "",
        category: Annotated[str | None, Query(max_length=100)] = None,
        max_price_brl: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        limit: Annotated[int, Query(ge=1, le=30)] = 8,
    ):
        return {
            "products": service.catalog.search_products(
                query,
                category=category,
                max_price_brl=max_price_brl,
                available_only=True,
                limit=limit,
            )
        }

    @application.get("/api/policies/document")
    def policy_document(service: Service):
        return FileResponse(
            service.settings.data_dir / "politicas_da_loja.pdf", media_type="application/pdf"
        )

    application.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    return application


app = create_app()
