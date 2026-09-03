from unittest.mock import Mock
from time import perf_counter

import httpcore
import pytest

from app.api.v1.endpoints import compile as compile_endpoint
from app.api.v1.endpoints.compile import CompileRequest
from app.core.exceptions import OptimizationSolverError
from app.schemas.explanation import DesignExplanation
from app.schemas.intent import CompilerIntent, RoomIntent
from app.services.ai.explainer import explain_layout
from app.services.ai.parser import parse_requirements


def _intent() -> CompilerIntent:
    return CompilerIntent(
        plot_width=44,
        plot_depth=42,
        rooms=[RoomIntent(room_type="bedroom")],
    )


def _compiled_result() -> dict:
    return {
        "success": True,
        "metadata": {"plot_width": 44.0, "plot_depth": 42.0, "floors_count": 1},
        "layout": {},
        "boundaries": {},
        "geometry": {},
        "floors": {},
        "metrics": {},
        "render_tree": {},
    }


def test_gemini_success_allows_gemini_explanation(monkeypatch):
    explanation = DesignExplanation(
        overall_concept="AI explanation",
        kitchen_placement="AI kitchen",
        plumbing_efficiency="AI plumbing",
        vastu_compliance="AI vastu",
        circulation_efficiency="AI circulation",
    )
    client = Mock()
    client.create.side_effect = [_intent(), explanation]
    monkeypatch.setattr(compile_endpoint, "compile_blueprint", lambda payload: _compiled_result())

    result = compile_endpoint.compile_layout(
        CompileRequest(prompt="1 bedroom on a 44x42 plot"),
        client=client,
    )

    assert result["explanation"]["overall_concept"] == "AI explanation"
    assert client.create.call_count == 2


def test_compiler_quota_failure_uses_local_explanation_without_duplicate_call(monkeypatch):
    client = Mock()
    client.create.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED")
    monkeypatch.setattr(compile_endpoint, "compile_blueprint", lambda payload: _compiled_result())

    result = compile_endpoint.compile_layout(
        CompileRequest(prompt="1 bedroom on a 44x42 plot"),
        client=client,
    )

    assert result["success"] is True
    assert "customized" in result["explanation"]["overall_concept"].lower()
    assert client.create.call_count == 1


@pytest.mark.parametrize(
    "failure_case",
    [
        (TimeoutError("Gemini request timed out"), "timeout"),
        (httpcore.RemoteProtocolError("server disconnected"), "network"),
    ],
)
def test_provider_network_failure_falls_back_without_waiting(monkeypatch, failure_case):
    failure, failure_type = failure_case
    client = Mock()
    client.create.side_effect = failure
    monkeypatch.setattr(compile_endpoint, "compile_blueprint", lambda payload: _compiled_result())
    captured_state = {}
    original_explain_layout = compile_endpoint.explain_layout

    def capture_state(prompt, layout_data, client=None, ai_state=None):
        captured_state.update(ai_state or {})
        return original_explain_layout(prompt, layout_data, client, ai_state)

    monkeypatch.setattr(compile_endpoint, "explain_layout", capture_state)

    started = perf_counter()
    result = compile_endpoint.compile_layout(
        CompileRequest(prompt="1 bedroom on a 44x42 plot"),
        client=client,
    )
    elapsed = perf_counter() - started

    assert result["success"] is True
    assert client.create.call_count == 1
    assert elapsed < 1.0
    assert captured_state["failure_type"] == failure_type


def test_normal_compiler_validation_failure_preserves_local_fallback():
    client = Mock()

    def fail_once(**kwargs):
        assert kwargs["max_retries"] == 0
        raise ValueError("validation failed")

    client.create.side_effect = fail_once
    ai_state = {"compiler_failed": False, "quota_exhausted": False, "failure_type": None}

    intent = parse_requirements("1 bedroom on a 44x42 plot", client, ai_state)
    explanation_client = Mock()
    explanation = explain_layout("1 bedroom", _compiled_result(), explanation_client, ai_state)

    assert intent.plot_width == 44.0
    assert ai_state["compiler_failed"] is True
    assert ai_state["quota_exhausted"] is False
    assert ai_state["failure_type"] == "schema"
    assert explanation_client.create.call_count == 0
    assert "customized" in explanation.overall_concept.lower()


def test_optimizer_failure_keeps_existing_error_handling(monkeypatch):
    monkeypatch.setattr(
        compile_endpoint,
        "compile_blueprint",
        lambda payload: {"success": False, "error": "Optimization Constraint Solver Error: failed"},
    )

    with pytest.raises(OptimizationSolverError):
        compile_endpoint.compile_layout(
            CompileRequest(prompt="1 bedroom on a 44x42 plot"),
            client=None,
        )


def test_llm_client_uses_explicit_http_timeout(monkeypatch):
    from app.api import dependencies

    provider_client = object()
    from_openai = Mock(return_value=provider_client)
    monkeypatch.setattr(dependencies.instructor, "from_openai", from_openai)
    monkeypatch.setattr(dependencies.settings, "NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr(dependencies, "_llm_client", None)
    monkeypatch.setattr(dependencies, "_gemini_client", None)

    assert dependencies.get_llm_client() is provider_client
    assert from_openai.called