from types import SimpleNamespace

import pytest

from app.provider_errors import ProviderInputError, ProviderResponseError, ProviderTransportError
from app.providers import DeterministicPolicyProvider, OpenAICompatiblePolicyProvider


def chunk():
    return {
        "id": "chunk-1",
        "document_id": "doc-1",
        "ordinal": 0,
        "text": "Akses layanan publik harus adil dan transparan.",
        "char_start": 0,
        "char_end": 48,
    }


def project():
    return {"id": "project-1", "name": "Kebijakan Akses", "objective": "Menilai akses layanan"}


class InvalidJsonCompletions:
    def create(self, **_kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))])


class CapturingCompletions:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        payload = __import__("json").loads(kwargs["messages"][1]["content"])
        fallback = payload["context"]["fallback"]
        fallback["analysis_summary"] = "Ontology khusus berdasarkan bukti terpilih."
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=__import__("json").dumps(fallback),
        ))])


def client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_deterministic_provider_validates_all_operation_contracts():
    provider = DeterministicPolicyProvider()
    chunks = [chunk()]
    ontology = provider.ontology(project(), chunks)
    graph = provider.graph(project(), ontology, chunks)
    environment = provider.environment("sim-1", graph, {"rounds": 3})
    simulation = provider.simulate("sim-1", graph, environment["personas"], environment["config"])

    assert provider.report(project(), chunks, simulation["events"])["sections"]
    assert provider.answer({"question": "Apa risikonya?"}, {"simulation": simulation}, chunks)["text"]
    assert provider.interview("Apa perhatian utama?", environment["personas"][:1], simulation["events"])["answers"]
    assert provider.graph_memory(graph, simulation["events"])["memory_revision"] == 1


def test_strict_input_contract_raises_classified_error():
    with pytest.raises(ProviderInputError) as captured:
        DeterministicPolicyProvider().ontology(
            {"id": "project-1", "name": "Nama", "objective": "Tujuan"},
            [{**chunk(), "ordinal": "0"}],
        )

    assert captured.value.category == "input_validation"
    assert captured.value.operation == "ontology"
    assert captured.value.retryable is False


def test_openai_declares_every_protocol_operation_without_inheritance():
    operations = {"ontology", "graph", "environment", "simulate", "report", "answer", "interview", "graph_memory"}
    assert operations <= OpenAICompatiblePolicyProvider.__dict__.keys()


def test_openai_fallback_policy_is_explicit():
    fallback = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(InvalidJsonCompletions()), fallback_policy="deterministic"
    )
    assert fallback.ontology(project(), [chunk()])["generated_by"] == "deterministic-grounded"

    strict = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(InvalidJsonCompletions()), fallback_policy="raise"
    )
    with pytest.raises(ProviderResponseError) as captured:
        strict.ontology(project(), [chunk()])
    assert captured.value.category == "invalid_response"


def test_openai_ontology_bounds_context_and_output_tokens():
    completions = CapturingCompletions()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise", max_output_tokens=1234,
    )
    chunks = [{**chunk(), "id": f"chunk-{index}", "ordinal": index} for index in range(10)]

    result = provider.ontology(project(), chunks)

    call = completions.calls[0]
    payload = __import__("json").loads(call["messages"][1]["content"])
    assert call["max_tokens"] == 1234
    assert "response_format" not in call
    assert len(payload["context"]["chunks"]) == 6
    assert result["generated_by"] == "openai-compatible"
    assert result["analysis_summary"] == "Ontology khusus berdasarkan bukti terpilih."


def test_openai_timeout_is_classified_for_worker_retry():
    completions = CapturingCompletions(TimeoutError("upstream timeout"))
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )

    with pytest.raises(ProviderTransportError) as captured:
        provider.ontology(project(), [chunk()])

    assert captured.value.category == "transport"
    assert captured.value.retryable is True


def test_openai_accepts_fenced_json_from_compatible_gateway():
    class FencedCompletions(CapturingCompletions):
        def create(self, **kwargs):
            response = super().create(**kwargs)
            response.choices[0].message.content = f"```json\n{response.choices[0].message.content}\n```"
            return response

    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(FencedCompletions()), fallback_policy="raise",
    )

    assert provider.ontology(project(), [chunk()])["generated_by"] == "openai-compatible"


def test_openai_graph_uses_compact_refinements_and_preserves_topology():
    class GraphCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            payload = __import__("json").loads(kwargs["messages"][1]["content"])
            nodes = [
                {"id": item["id"], "label": item["label"], "summary": f"Spesifik: {item['summary']}"}
                for item in payload["context"]["nodes"]
            ]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=__import__("json").dumps({"nodes": nodes}),
            ))])

    completions = GraphCompletions()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )
    chunks = [chunk()]
    ontology = DeterministicPolicyProvider().ontology(project(), chunks)
    fallback = DeterministicPolicyProvider().graph(project(), ontology, chunks)

    result = provider.graph(project(), ontology, chunks)

    payload = __import__("json").loads(completions.calls[0]["messages"][1]["content"])
    assert "fallback" not in payload["context"]
    assert len(payload["context"]["chunks"][0]["text"]) <= 600
    assert result["edges"] == fallback["edges"]
    assert [node["id"] for node in result["nodes"]] == [node["id"] for node in fallback["nodes"]]
    assert all(node["summary"].startswith("Spesifik: ") for node in result["nodes"])
