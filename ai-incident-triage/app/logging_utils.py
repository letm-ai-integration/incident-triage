"""Shared lifecycle logging for nodes, agents, and subagents.

Provides consistent ``[NODE][ENTRY]``, ``[AGENT][ENTRY]``, ``[SUBAGENT][ENTRY]``
(and corresponding OUTPUT / EXIT / ERROR) log lines so the execution trace of
every pipeline run is unambiguous.
"""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger("app.lifecycle")


def entry(kind: str, name: str, detail: str = "") -> None:
    suffix = f" | {detail}" if detail else ""
    logger.info("[%s][ENTRY] %s%s", kind, name, suffix)


def output(kind: str, name: str, summary: str) -> None:
    logger.info("[%s][OUTPUT] %s | %s", kind, name, summary)


def exit_(kind: str, name: str) -> None:
    logger.info("[%s][EXIT] %s", kind, name)


def process(kind: str, name: str, detail: str) -> None:
    """Log a concise, meaningful progress/achievement line for the callable.

    ``detail`` should summarise what the callable actually did (e.g. how many
    documents were retrieved, which pods were seen) -- not dump large payloads.
    """
    logger.info("[%s][PROCESS] %s | %s", kind, name, detail)


def error(kind: str, name: str, exc: BaseException, detail: str = "") -> None:
    msg = f"{type(exc).__name__}: {exc}"
    if detail:
        msg = f"{detail} -- {msg}"
    logger.error("[%s][ERROR] %s | %s", kind, name, msg)


def node_entry(name: str, detail: str = "") -> None:
    entry("NODE", name, detail)


def node_exit(name: str) -> None:
    exit_("NODE", name)


def node_error(name: str, exc: BaseException) -> None:
    error("NODE", name, exc)


def agent_entry(name: str, detail: str = "") -> None:
    entry("AGENT", name, detail)


def agent_output(name: str, summary: str) -> None:
    output("AGENT", name, summary)


def agent_exit(name: str) -> None:
    exit_("AGENT", name)


def agent_error(name: str, exc: BaseException, detail: str = "") -> None:
    error("AGENT", name, exc, detail)


def agent_process(name: str, detail: str) -> None:
    process("AGENT", name, detail)


def subagent_process(name: str, detail: str) -> None:
    process("SUBAGENT", name, detail)


def subagent_entry(name: str, detail: str = "") -> None:
    entry("SUBAGENT", name, detail)


def subagent_output(name: str, summary: str) -> None:
    output("SUBAGENT", name, summary)


def subagent_exit(name: str) -> None:
    exit_("SUBAGENT", name)


def subagent_error(name: str, exc: BaseException, detail: str = "") -> None:
    error("SUBAGENT", name, exc, detail)


def wrap_with_lifecycle(
    kind: str,
    name: str,
    node: Callable,
    *,
    detail_fn: Callable[..., str] | None = None,
) -> Callable:
    """Wrap a sync or async callable with ENTRY / EXIT / ERROR lifecycle logs.

    *kind* is typically ``"NODE"``, ``"AGENT"``, or ``"SUBAGENT"``.
    The wrapper preserves async-ness of the original callable.
    """
    entry_fn = entry
    exit_fn = exit_
    error_fn = error

    if inspect.iscoroutinefunction(node):

        @functools.wraps(node)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            detail = detail_fn(*args, **kwargs) if detail_fn else ""
            entry_fn(kind, name, detail)
            try:
                result = await node(*args, **kwargs)
            except Exception as exc:
                error_fn(kind, name, exc)
                raise
            exit_fn(kind, name)
            return result

        return _async_wrapper

    @functools.wraps(node)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        detail = detail_fn(*args, **kwargs) if detail_fn else ""
        entry_fn(kind, name, detail)
        try:
            result = node(*args, **kwargs)
        except Exception as exc:
            error_fn(kind, name, exc)
            raise
        exit_fn(kind, name)
        return result

    return _sync_wrapper
