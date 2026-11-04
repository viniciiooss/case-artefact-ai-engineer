"""Atendimento em português no terminal, com a mesma autorização do serviço HTTP."""

import shlex
from typing import Annotated

import typer
from rich.console import Console

from emporio.catalog import Catalog
from emporio.config import Settings
from emporio.retrieval import PolicyIndex
from emporio.service import (
    PROVIDER_ERROR_MESSAGES,
    AgentUnavailable,
    ChatService,
    VerificationFailed,
    VerificationRateLimited,
)
from emporio.sessions import SessionBusy, SessionNotFound

app = typer.Typer(
    help="Converse com a Mel, da Empório da Música.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console(markup=False)


def _service() -> ChatService:
    try:
        return ChatService(Settings())
    except Exception:
        console.print("Não foi possível iniciar. Confira a configuração e os arquivos de dados.")
        raise typer.Exit(1) from None


def _notice(service: ChatService):
    if service.settings.provider == "demo":
        console.print("Modo demo: simulador determinístico, sem conexão com uma LLM.")


def _response(response: dict):
    console.print(f"Mel: {response['message']}")
    sources = response.get("sources", [])
    if sources:
        console.print("Fontes consultadas:")
        for source in sources:
            page = f" · página {source['page']}" if source.get("page") else ""
            console.print(f"  • {source.get('title', 'Referência')}{page}")


def _error(exc: Exception):
    if isinstance(exc, VerificationFailed):
        message = "Não foi possível identificar o pedido com esses dados."
    elif isinstance(exc, VerificationRateLimited):
        message = "Muitas tentativas. Aguarde um minuto e tente novamente."
    elif isinstance(exc, SessionBusy):
        message = "Uma resposta já está sendo preparada nesta conversa."
    elif isinstance(exc, SessionNotFound):
        message = "Conversa não encontrada. Use /novo para começar outra."
    elif isinstance(exc, AgentUnavailable):
        message = PROVIDER_ERROR_MESSAGES.get(
            exc.code, "O atendimento está indisponível agora. Tente novamente em instantes."
        )
    else:
        message = "O atendimento está indisponível agora. Tente novamente em instantes."
    console.print(message)


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Endereço para escutar.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535, help="Porta HTTP.")] = 8000,
):
    """Inicie o chat no navegador."""
    import uvicorn

    uvicorn.run("emporio.api:app", host=host, port=port)


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Sua pergunta para a Mel.")],
    order_id: Annotated[int | None, typer.Option(min=1, help="Número do pedido.")] = None,
    email: Annotated[str | None, typer.Option(help="E-mail informado na compra.")] = None,
):
    """Faça uma pergunta em uma conversa temporária."""
    if (order_id is None) != (email is None):
        console.print("Informe --order-id e --email juntos para identificar o pedido.")
        raise typer.Exit(2)
    question = question.strip()
    if not 1 <= len(question) <= 4000:
        console.print("A pergunta deve ter entre 1 e 4000 caracteres.")
        raise typer.Exit(2)
    service = _service()
    _notice(service)
    session = service.create_session()
    try:
        if order_id is not None:
            service.verify_order(session["session_id"], order_id, email.strip())
        _response(service.chat(session["session_id"], question))
    except (
        AgentUnavailable,
        VerificationFailed,
        VerificationRateLimited,
        SessionBusy,
        SessionNotFound,
    ) as exc:
        _error(exc)
        raise typer.Exit(1) from None
    finally:
        service.sessions.delete(session["session_id"])
        service.close()


@app.command()
def chat():
    """Abra uma conversa; /verificar NÚMERO EMAIL identifica seu pedido."""
    service = _service()
    _notice(service)
    console.print("Mel: Oi! Como posso ajudar? /verificar NÚMERO EMAIL · /novo · /sair")
    session = service.create_session()
    while True:
        try:
            message = console.input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("Até mais!")
            break
        if not message:
            continue
        if message.casefold() == "/sair":
            console.print("Até mais!")
            break
        if message.casefold() == "/novo":
            service.sessions.delete(session["session_id"])
            session = service.create_session()
            console.print("Nova conversa iniciada. Como posso ajudar?")
            continue
        try:
            if message.casefold().startswith("/verificar"):
                try:
                    parts = shlex.split(message)
                    if len(parts) != 3 or parts[0].casefold() != "/verificar":
                        raise ValueError
                    order_id = int(parts[1])
                    email = parts[2].strip()
                    if order_id <= 0 or len(email) > 254 or "@" not in email:
                        raise ValueError
                except ValueError:
                    console.print("Use /verificar NÚMERO EMAIL com os dados da compra.")
                    continue
                service.verify_order(session["session_id"], order_id, email)
                console.print("Pedido identificado nesta conversa. Pode perguntar à Mel.")
            elif message.startswith("/"):
                console.print("Comandos disponíveis: /verificar NÚMERO EMAIL · /novo · /sair")
            elif len(message) > 4000:
                console.print("A mensagem deve ter no máximo 4000 caracteres.")
            else:
                _response(service.chat(session["session_id"], message))
        except (
            AgentUnavailable,
            VerificationFailed,
            VerificationRateLimited,
            SessionBusy,
            SessionNotFound,
        ) as exc:
            _error(exc)
    service.close()


@app.command()
def ingest():
    """Valide o snapshot e carregue o catálogo de forma idempotente por hash."""
    try:
        settings = Settings()
        catalog = Catalog(settings.data_dir, settings.state_dir / "catalog.sqlite3")
        policies = PolicyIndex(settings.data_dir / "politicas_da_loja.pdf")
        counts = catalog.counts()
        console.print(
            f"Carga idempotente por hash: {counts['products']} produtos, "
            f"{counts['orders']} pedidos, {len(policies.chunks)} trechos de políticas."
        )
        console.print(f"Catálogo: {catalog.fingerprint}")
        console.print(f"Políticas: {policies.fingerprint}")
    except Exception:
        console.print("Não foi possível carregar os dados. Confira a configuração e os arquivos.")
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
