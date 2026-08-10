"""Human-in-the-loop approval: interrupt/resume integration tests."""

from __future__ import annotations

import asyncio

from langgraph.types import Command

from app.domain.models import ApprovalStatus
from app.graph import compile_workflow, create_checkpointer


def _payload(resolved: bool = True) -> dict:
    return {
        "title": "API latency spike",
        "description": "Elevated error rate detected on the checkout service",
        "raw": {
            "resolved": resolved,
            "logs": ["ERROR: checkout timeout"],
        },
    }


class TestInterruptResume:
    def test_interrupt_then_resume(self) -> None:
        async def run() -> None:
            checkpointer = create_checkpointer()
            compiled = compile_workflow(checkpointer=checkpointer)
            cfg = {"configurable": {"thread_id": "interrupt-1"}}

            first = await compiled.ainvoke({"incident": _payload()}, cfg)
            assert "__interrupt__" in first
            interrupt = first["__interrupt__"][0]
            assert "Approve" in interrupt.value["prompt"]

            resumed = await compiled.ainvoke(
                Command(resume={"approved": True, "reviewer": "sre-1"}), cfg
            )
            assert resumed["approval"].status == ApprovalStatus.APPROVED
            assert resumed["approval"].reviewer == "sre-1"
            assert resumed.get("notification")

        asyncio.run(run())

    def test_interrupt_then_reject(self) -> None:
        async def run() -> None:
            checkpointer = create_checkpointer()
            compiled = compile_workflow(checkpointer=checkpointer)
            cfg = {"configurable": {"thread_id": "interrupt-2"}}

            await compiled.ainvoke({"incident": _payload()}, cfg)
            resumed = await compiled.ainvoke(
                Command(resume={"approved": False, "comments": "verify root cause"}),
                cfg,
            )
            assert resumed["approval"].status == ApprovalStatus.REJECTED
            assert resumed["approval"].comments == "verify root cause"

        asyncio.run(run())

    def test_resume_requires_checkpointer(self) -> None:
        async def run() -> None:
            # Without a checkpointer, compile_workflow supplies one automatically.
            compiled = compile_workflow()
            cfg = {"configurable": {"thread_id": "interrupt-3"}}

            first = await compiled.ainvoke({"incident": _payload()}, cfg)
            assert "__interrupt__" in first

            resumed = await compiled.ainvoke(Command(resume={"approved": True}), cfg)
            assert resumed["approval"].status == ApprovalStatus.APPROVED
            assert resumed.get("notification")

        asyncio.run(run())
