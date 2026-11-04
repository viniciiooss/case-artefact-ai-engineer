"""Tracing opcional; exporta execução e uso, sem conteúdo de conversas."""

import hashlib
import logging
import os

from emporio.config import Settings

logger = logging.getLogger(__name__)


def _mask_spans(*, params):
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    # O estado do grafo contém mensagens e resultados completos das ferramentas.
    private_prefixes = (
        "langfuse.observation.input",
        "langfuse.observation.output",
        "langfuse.observation.metadata",
        "langfuse.trace.metadata",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "exception.",
    )
    return MaskOtelSpansResult(
        span_patches={
            identifier: OtelSpanPatch(
                delete_attributes=tuple(
                    key for key in span.attributes if key.startswith(private_prefixes)
                )
            )
            for identifier, span in params.spans.items()
        }
    )


class Observability:
    def __init__(self, settings: Settings):
        self.client = None
        self._handler = None
        self._public_key = None
        if not settings.langfuse_enabled:
            return
        try:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler

            class SafeCallbackHandler(CallbackHandler):
                # O status OTel também contém a exceção; masking de atributos não o cobre.
                def on_chain_error(self, error, **kwargs):
                    super().on_chain_error(RuntimeError("agent_failure"), **kwargs)

                def on_llm_error(self, error, **kwargs):
                    super().on_llm_error(RuntimeError("provider_failure"), **kwargs)

                def on_tool_error(self, error, **kwargs):
                    super().on_tool_error(RuntimeError("tool_failure"), **kwargs)

            self._public_key = settings.langfuse_public_key.get_secret_value()
            # O SDK processa mídia ANTES do masking; este atendimento aceita somente texto.
            os.environ["LANGFUSE_MEDIA_UPLOAD_ENABLED"] = "false"
            self.client = Langfuse(
                public_key=self._public_key,
                secret_key=settings.langfuse_secret_key.get_secret_value(),
                base_url=settings.langfuse_base_url,
                environment=settings.langfuse_environment,
                mask_otel_spans=_mask_spans,
                timeout=5,
            )
            self._handler = SafeCallbackHandler
        except Exception as exc:
            logger.warning("tracing_unavailable type=%s", type(exc).__name__)

    def config(self, session_id: str) -> dict:
        if self.client is None or self._handler is None:
            return {}
        try:
            return {
                "callbacks": [self._handler(public_key=self._public_key)],
                "run_name": "emporio.chat",
                "tags": ["emporio", "artefact"],
                "metadata": {
                    "langfuse_session_id": hashlib.sha256(session_id.encode()).hexdigest()
                },
            }
        except Exception as exc:
            logger.warning("tracing_unavailable type=%s", type(exc).__name__)
            return {}

    def close(self):
        if self.client is not None:
            try:
                self.client.flush()
            except Exception as exc:
                logger.warning("tracing_flush_failed type=%s", type(exc).__name__)
