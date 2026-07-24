from types import SimpleNamespace

import pytest

from app.provider_errors import ProviderInputError, ProviderResponseError
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
