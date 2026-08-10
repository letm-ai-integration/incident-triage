"""Public API and export surface tests for the graph package."""

from __future__ import annotations


class TestPublicImports:
    def test_builder_import(self) -> None:
        from app.graph.builder import addEdge, addNode

        assert callable(addNode)
        assert callable(addEdge)

    def test_package_import(self) -> None:
        from app.graph import addEdge, addNode

        assert callable(addNode)
        assert callable(addEdge)

    def test_package_public_functions(self) -> None:
        from app.graph import (
            addConditionalEdge,
            compileGraph,
            createGraph,
            validateGraph,
        )

        assert callable(addConditionalEdge)
        assert callable(compileGraph)
        assert callable(createGraph)
        assert callable(validateGraph)

    def test_package_start_end(self) -> None:
        from app.graph import END, START

        assert START == "__start__"
        assert END == "__end__"

    def test_workflow_functions(self) -> None:
        from app.graph import build_workflow, compile_workflow, create_checkpointer

        assert callable(build_workflow)
        assert callable(compile_workflow)
        assert callable(create_checkpointer)

    def test_no_duplicate_builder_module(self) -> None:
        import app.graph.builder
        from app.graph import addNode

        assert addNode is app.graph.builder.addNode
