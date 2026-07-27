import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.provider_contracts import EnvironmentOutput, SimulationOutput
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


def simulation_inputs(rounds=3):
    deterministic = DeterministicPolicyProvider()
    chunks = [chunk()]
    ontology = deterministic.ontology(project(), chunks)
    graph = deterministic.graph(project(), ontology, chunks)
    environment = deterministic.environment("sim-1", graph, {"rounds": rounds})
    return graph, environment["personas"], environment["config"]


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


def test_openai_environment_uses_compact_batches_and_preserves_local_structure():
    class EnvironmentCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            if "personas" not in context:
                response = {
                    "assumptions": ["Asumsi khusus"],
                    "generation_reasoning": "Alasan khusus berdasarkan graph.",
                    "rounds": 999,
                    "channels": [],
                }
            else:
                response = {"personas": [
                    {
                        "id": item["id"],
                        "name": f"Nama {item['id']}",
                        "role": "Peran khusus",
                        "profile": f"Profil khusus {item['id']}",
                        "stance": "Kritis",
                        "group": "Kelompok palsu",
                        "source_node_ids": ["node-palsu"],
                        "citations": [],
                    }
                    for item in reversed(context["personas"])
                ]}
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(response),
            ))])

    graph, _, _ = simulation_inputs()
    requested = {"rounds": 8, "socialization": "Tinggi", "response_mode": "Adaptif"}
    fallback = DeterministicPolicyProvider().environment("sim-1", graph, requested)
    completions = EnvironmentCompletions()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )

    result = provider.environment("sim-1", graph, requested)

    assert len(completions.calls) == 4
    config_context = json.loads(completions.calls[0]["messages"][1]["content"])["context"]
    assert "fallback" not in config_context
    assert "personas" not in config_context
    assert all("citations" not in node for node in config_context["graph_nodes"])
    for call in completions.calls[1:]:
        context = json.loads(call["messages"][1]["content"])["context"]
        assert len(context["personas"]) == 10
        assert all(set(persona) == {
            "id", "name", "group", "role", "profile", "stance", "concern",
        } for persona in context["personas"])
        assert all("citations" not in node for node in context["graph_nodes"])

    assert result["persona_count"] == 30
    assert result["config"]["assumptions"] == ["Asumsi khusus"]
    assert result["config"]["generation_reasoning"] == "Alasan khusus berdasarkan graph."
    assert result["config"]["generated_by"] == "openai-compatible"
    for field in (
        "rounds", "socialization", "response_mode", "channels", "influence_mode",
        "events_per_round", "seed", "version", "overrides",
    ):
        assert result["config"][field] == fallback["config"][field]
    assert [persona["id"] for persona in result["personas"]] == [
        persona["id"] for persona in fallback["personas"]
    ]
    for persona, local in zip(result["personas"], fallback["personas"], strict=True):
        assert persona["name"] == f"Nama {persona['id']}"
        assert persona["role"] == "Peran khusus"
        assert persona["profile"] == f"Profil khusus {persona['id']}"
        assert persona["stance"] == "Kritis"
        for field in (
            "id", "group", "stakeholder_group", "concern", "concerns", "topics", "influence",
            "active", "count", "source_node_ids", "citations",
        ):
            assert persona[field] == local[field]


@pytest.mark.parametrize("response_kind", ["missing", "duplicate", "unknown"])
def test_openai_environment_rejects_changed_persona_id_sets(response_kind):
    class InvalidPersonaCompletions:
        def create(self, **kwargs):
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            if "personas" not in context:
                response = {"assumptions": [], "generation_reasoning": "Alasan valid."}
            else:
                personas = [
                    {
                        "id": item["id"], "name": item["name"], "role": item["role"],
                        "profile": item["profile"], "stance": item["stance"],
                    }
                    for item in context["personas"]
                ]
                if response_kind == "missing":
                    personas.pop()
                elif response_kind == "duplicate":
                    personas[-1]["id"] = personas[0]["id"]
                else:
                    personas[-1]["id"] = "persona-unknown"
                response = {"personas": personas}
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(response),
            ))])

    graph, _, _ = simulation_inputs()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(InvalidPersonaCompletions()), fallback_policy="raise",
    )

    with pytest.raises(ProviderResponseError, match="preserve every input persona ID"):
        provider.environment("sim-1", graph, {"rounds": 3})


def test_openai_environment_falls_back_atomically_when_later_batch_times_out():
    class LaterEnvironmentTimeout:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 3:
                raise TimeoutError("upstream timeout")
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            response = (
                {"assumptions": ["Refined"], "generation_reasoning": "Refined reasoning."}
                if "personas" not in context else
                {"personas": [
                    {
                        "id": item["id"], "name": "Refined", "role": item["role"],
                        "profile": item["profile"], "stance": item["stance"],
                    }
                    for item in context["personas"]
                ]}
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(response),
            ))])

    graph, _, _ = simulation_inputs()
    requested = {"rounds": 3}
    fallback = DeterministicPolicyProvider().environment("sim-1", graph, requested)
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(LaterEnvironmentTimeout()), fallback_policy="deterministic",
    )

    assert provider.environment("sim-1", graph, requested) == fallback


def test_environment_output_rejects_duplicate_persona_ids():
    graph, _, _ = simulation_inputs()
    environment = DeterministicPolicyProvider().environment("sim-1", graph, {"rounds": 3})
    environment["personas"][1]["id"] = environment["personas"][0]["id"]

    with pytest.raises(ValidationError, match="persona IDs must be unique"):
        EnvironmentOutput.model_validate(environment, strict=True)


def test_openai_simulate_uses_compact_round_batches_and_preserves_local_structure():
    class SimulationCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            payload = json.loads(kwargs["messages"][1]["content"])
            events = [
                {
                    "id": item["id"],
                    "statement": f"Respons spesifik {item['id']}",
                    "stance": "Kritis",
                    "risk_narrative": "Risiko spesifik",
                    "round": 999,
                    "persona_id": "persona-palsu",
                    "source_node_ids": ["node-palsu"],
                    "citations": [],
                }
                for item in reversed(payload["context"]["events"])
            ]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"events": events}),
            ))])

    graph, personas, config = simulation_inputs()
    fallback = DeterministicPolicyProvider().simulate("sim-1", graph, personas, config)
    completions = SimulationCompletions()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )

    result = provider.simulate("sim-1", graph, personas, config)

    assert len(completions.calls) == config["rounds"]
    for call in completions.calls:
        context = json.loads(call["messages"][1]["content"])["context"]
        assert "fallback" not in context
        assert len(context["events"]) == config["events_per_round"]
        assert all(set(event) == {
            "id", "persona_id", "group", "concerns", "statement", "stance", "risk_narrative",
        } for event in context["events"])
        assert all("citations" not in persona for persona in context["personas"])
        assert all("citations" not in node for node in context["graph_nodes"])

    assert [event["id"] for event in result["events"]] == [event["id"] for event in fallback["events"]]
    for event, local in zip(result["events"], fallback["events"], strict=True):
        assert event["statement"] == f"Respons spesifik {event['id']}"
        assert event["content"] == event["statement"]
        assert event["stance"] == "Kritis"
        assert event["risk_narrative"] == "Risiko spesifik"
        for field in (
            "id", "sequence", "round", "time", "channel", "persona_id", "persona", "persona_name",
            "group", "type", "event_type", "concerns", "influence_source", "source_node_ids", "citations",
            "graph_revision", "config_version",
        ):
            assert event[field] == local[field]


@pytest.mark.parametrize("response_kind", ["missing", "duplicate", "unknown"])
def test_openai_simulate_rejects_changed_event_id_sets(response_kind):
    class InvalidEventCompletions:
        def create(self, **kwargs):
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            events = [
                {
                    "id": item["id"], "statement": item["statement"],
                    "stance": item["stance"], "risk_narrative": item["risk_narrative"],
                }
                for item in context["events"]
            ]
            if response_kind == "missing":
                events.pop()
            elif response_kind == "duplicate":
                events[-1]["id"] = events[0]["id"]
            else:
                events[-1]["id"] = "event-unknown"
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"events": events}),
            ))])

    graph, personas, config = simulation_inputs()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(InvalidEventCompletions()), fallback_policy="raise",
    )

    with pytest.raises(ProviderResponseError, match="preserve every input event ID"):
        provider.simulate("sim-1", graph, personas, config)


def test_openai_simulate_falls_back_atomically_when_later_batch_times_out():
    class LaterTimeoutCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise TimeoutError("upstream timeout")
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            events = [
                {
                    "id": item["id"], "statement": "Refined before timeout",
                    "stance": item["stance"], "risk_narrative": item["risk_narrative"],
                }
                for item in context["events"]
            ]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"events": events}),
            ))])

    graph, personas, config = simulation_inputs()
    fallback = DeterministicPolicyProvider().simulate("sim-1", graph, personas, config)
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(LaterTimeoutCompletions()), fallback_policy="deterministic",
    )

    assert provider.simulate("sim-1", graph, personas, config) == fallback


def test_openai_simulate_later_timeout_is_retryable_in_strict_mode():
    graph, personas, config = simulation_inputs()
    completions = CapturingCompletions(TimeoutError("upstream timeout"))
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )

    with pytest.raises(ProviderTransportError) as captured:
        provider.simulate("sim-1", graph, personas, config)

    assert captured.value.operation == "simulate"
    assert captured.value.retryable is True


def test_simulation_output_rejects_duplicate_ids_and_noncontiguous_sequences():
    graph, personas, config = simulation_inputs(rounds=1)
    simulation = DeterministicPolicyProvider().simulate("sim-1", graph, personas, config)

    duplicate = json.loads(json.dumps(simulation))
    duplicate["events"][1]["id"] = duplicate["events"][0]["id"]
    with pytest.raises(ValidationError, match="event IDs must be unique"):
        SimulationOutput.model_validate(duplicate, strict=True)

    noncontiguous = json.loads(json.dumps(simulation))
    noncontiguous["events"][1]["sequence"] = 99
    with pytest.raises(ValidationError, match="sequences must be contiguous and ordered"):
        SimulationOutput.model_validate(noncontiguous, strict=True)


def test_openai_graph_memory_uses_compact_refinements_and_preserves_topology():
    class GraphMemoryCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            context = json.loads(kwargs["messages"][1]["content"])["context"]
            nodes = [
                {"id": item["id"], "label": f"Risiko {item['id']}", "summary": f"Spesifik {item['id']}"}
                for item in reversed(context["nodes"])
            ]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps({"nodes": nodes}),
            ))])

    graph, personas, config = simulation_inputs()
    events = DeterministicPolicyProvider().simulate("sim-1", graph, personas, config)["events"]
    fallback = DeterministicPolicyProvider().graph_memory(graph, events)
    completions = GraphMemoryCompletions()
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(completions), fallback_policy="raise",
    )

    result = provider.graph_memory(graph, events)

    context = json.loads(completions.calls[0]["messages"][1]["content"])["context"]
    assert "graph" not in context
    assert "fallback" not in context
    assert len(context["nodes"]) <= 6
    assert all(set(node) == {"id", "label", "summary", "memory_source"} for node in context["nodes"])
    assert all(set(event) == {"id", "group", "statement", "stance", "concerns"} for event in context["events"])
    assert result["edges"] == fallback["edges"]
    assert result["memory_event_ids"] == fallback["memory_event_ids"]
    assert [node["id"] for node in result["nodes"]] == [node["id"] for node in fallback["nodes"]]
    for node, local in zip(result["nodes"], fallback["nodes"], strict=True):
        if node.get("memory_source"):
            assert node["label"] == f"Risiko {node['id']}"
            assert node["summary"] == f"Spesifik {node['id']}"
            assert node["citations"] == local["citations"]
            assert node["memory_source"] == local["memory_source"]
        else:
            assert node == local


def test_openai_graph_memory_timeout_falls_back_atomically():
    graph, personas, config = simulation_inputs()
    events = DeterministicPolicyProvider().simulate("sim-1", graph, personas, config)["events"]
    fallback = DeterministicPolicyProvider().graph_memory(graph, events)
    provider = OpenAICompatiblePolicyProvider(
        "unused", "model", client=client(CapturingCompletions(TimeoutError("upstream timeout"))),
        fallback_policy="deterministic",
    )

    assert provider.graph_memory(graph, events) == fallback
