"""External observability integrations, as opposed to app/graph/tracing.py's
internal event-bus tracing (which feeds the live Streamlit trace panel).

LangSmith needs no code here: LangChain auto-instruments every LLM/tool call
from ``LANGCHAIN_TRACING_V2``/``LANGCHAIN_API_KEY``/``LANGCHAIN_PROJECT`` env
vars alone. Langfuse does not auto-instrument -- it needs an explicit
``langfuse.langchain.CallbackHandler`` in the graph invocation's
``config["callbacks"]`` list, which is what this module provides.
"""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_langfuse_client_initialized = False


def get_langfuse_callback_handlers() -> list:
    """Callback handlers for Langfuse tracing, or ``[]`` when unconfigured.

    Append the result to a graph invocation's ``config["callbacks"]`` --
    LangChain/LangGraph propagate callbacks to every nested LLM/tool call
    made during that run (the same mechanism app/graph/tracing.py's
    ``TracingCallbackHandler`` already relies on), so this needs no changes
    anywhere else in the pipeline.

    Credentials are passed explicitly rather than left to the Langfuse SDK's
    own ``os.environ`` lookup, since this app never calls ``load_dotenv()``.
    """
    settings = get_settings()
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return []

    global _langfuse_client_initialized
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.warning("[telemetry.tracing] langfuse is configured but not installed")
        return []

    try:
        if not _langfuse_client_initialized:
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_base_url,
            )
            _langfuse_client_initialized = True
        return [CallbackHandler(public_key=settings.langfuse_public_key)]
    except Exception:
        logger.exception("[telemetry.tracing] failed to initialize Langfuse -- tracing disabled for this run")
        return []


__all__ = ["get_langfuse_callback_handlers"]
