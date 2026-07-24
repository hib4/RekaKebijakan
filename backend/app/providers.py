from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections import Counter
from functools import wraps
from typing import Callable, Protocol

from pydantic import ValidationError

from .provider_contracts import PROVIDER_INPUTS, PROVIDER_OUTPUTS, FallbackPolicy
from .provider_errors import (
    ProviderError,
    ProviderInputError,
    ProviderOutputError,
    ProviderResponseError,
    ProviderTransportError,
)


GROUPS = ["Pemerintah daerah", "Pelaku usaha", "Warga terdampak", "Akademisi", "Masyarakat sipil", "Media lokal"]
STOPWORDS = {
    "yang", "dan", "atau", "dengan", "untuk", "dari", "pada", "dalam", "adalah", "akan", "ini", "itu",
    "harus", "dapat", "oleh", "sebagai", "ke", "di", "lebih", "agar", "serta", "kebijakan",
}


def validated(operation: str):
    input_model = PROVIDER_INPUTS[operation]
    output_model = PROVIDER_OUTPUTS[operation]

    def decorate(function: Callable):
        signature = inspect.signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            values = dict(signature.bind(*args, **kwargs).arguments)
            values.pop("self", None)
            try:
                input_model.model_validate(values, strict=True)
            except ValidationError as error:
                raise ProviderInputError(operation, "input contract rejected payload", details=error.errors()) from error
            result = function(*args, **kwargs)
            try:
                return output_model.model_validate(result, strict=True).model_dump(mode="python", exclude_none=True)
            except ValidationError as error:
                raise ProviderOutputError(operation, "output contract rejected payload", details=error.errors()) from error

        return wrapped

    return decorate


def citation(chunk: dict) -> dict:
    return {
        "source_type": "document_chunk",
        "source_id": chunk["id"],
        "chunk_id": chunk["id"],
        "document_id": chunk["document_id"],
        "locator": {"ordinal": chunk["ordinal"], "char_start": chunk["char_start"], "char_end": chunk["char_end"]},
        "quote": chunk["text"][:240],
        "label": f"Dokumen {chunk['document_id']} bagian {chunk['ordinal'] + 1}",
    }


def retrieve_chunks(query: str, chunks: list[dict], limit: int = 5) -> list[dict]:
    terms = {word for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", query.lower()) if word not in STOPWORDS}
    ranked = sorted(
        chunks,
        key=lambda chunk: (
            -sum(chunk["text"].lower().count(term) for term in terms),
            chunk["document_id"],
            chunk["ordinal"],
        ),
    )
    matched = [chunk for chunk in ranked if any(term in chunk["text"].lower() for term in terms)]
    return (matched or ranked)[:limit]


class PolicyProvider(Protocol):
    name: str

    def ontology(self, project: dict, chunks: list[dict]) -> dict: ...
    def graph(self, project: dict, ontology: dict, chunks: list[dict]) -> dict: ...
    def environment(self, simulation_id: str, graph: dict, config: dict) -> dict: ...
    def simulate(self, simulation_id: str, graph: dict, personas: list[dict], config: dict) -> dict: ...
    def report(self, project: dict, chunks: list[dict], events: list[dict]) -> dict: ...
    def answer(self, payload: dict, state: dict, chunks: list[dict]) -> dict: ...
    def interview(self, question: str, personas: list[dict], events: list[dict]) -> dict: ...
    def graph_memory(self, graph: dict, events: list[dict]) -> dict: ...


class DeterministicPolicyProvider:
    name = "deterministic-grounded"

    @staticmethod
    def _terms(chunks: list[dict], limit: int = 8) -> list[str]:
        words = re.findall(r"[A-Za-zÀ-ÿ]{4,}", " ".join(chunk["text"].lower() for chunk in chunks))
        return [word for word, _ in Counter(word for word in words if word not in STOPWORDS).most_common(limit)]

    @validated("ontology")
    def ontology(self, project: dict, chunks: list[dict]) -> dict:
        terms = self._terms(chunks)
        return {
            "version": 1,
            "entity_types": [
                {"name": name, "description": description}
                for name, description in (
                    ("Policy", "Kebijakan atau program yang dianalisis"),
                    ("Stakeholder", "Kelompok yang memengaruhi atau terdampak"),
                    ("Issue", "Isu yang ditemukan dalam sumber"),
                    ("Risk", "Risiko implementasi atau distribusi dampak"),
                    ("Outcome", "Hasil yang diharapkan"),
                )
            ],
            "relation_types": [
                {"name": "RESPONDS_TO", "source_types": ["Stakeholder"], "target_types": ["Policy", "Issue"]},
                {"name": "RAISES", "source_types": ["Stakeholder"], "target_types": ["Issue", "Risk"]},
                {"name": "AFFECTS", "source_types": ["Policy", "Issue"], "target_types": ["Stakeholder", "Outcome"]},
            ],
            "analysis_summary": f"Ontology kebijakan berfokus pada {', '.join(terms[:5]) or project['objective']}.",
            "citations": [citation(chunk) for chunk in chunks[:3]],
            "generated_by": self.name,
        }

    @validated("graph")
    def graph(self, project: dict, ontology: dict, chunks: list[dict]) -> dict:
        terms = self._terms(chunks, 6) or ["implementasi", "akses", "dampak"]
        nodes = [{
            "id": "policy", "label": project["name"], "type": "Policy", "summary": project["objective"],
            "x": 380, "y": 220, "citations": [citation(chunks[0])] if chunks else [],
        }]
        for index, group in enumerate(GROUPS):
            source = chunks[index % len(chunks)] if chunks else None
            nodes.append({
                "id": f"stakeholder-{index + 1}", "label": group, "type": "Stakeholder", "group": group,
                "summary": f"Kelompok yang terkait dengan isu {terms[index % len(terms)]}.",
                "x": 80 + (index % 3) * 300, "y": 50 + (index // 3) * 340,
                "citations": [citation(source)] if source else [],
            })
        for index, term in enumerate(terms):
            source = chunks[index % len(chunks)] if chunks else None
            nodes.append({
                "id": f"issue-{index + 1}", "label": term.title(), "type": "Issue",
                "summary": f"Isu '{term}' teridentifikasi dari dokumen kebijakan.",
                "x": 130 + (index % 3) * 280, "y": 150 + (index // 3) * 180,
                "citations": [citation(source)] if source else [],
            })
        edges = []
        for index in range(6):
            issue = f"issue-{index % len(terms) + 1}"
            edges.extend([
                {"id": f"edge-{index * 2 + 1}", "source": f"stakeholder-{index + 1}", "target": "policy", "type": "RESPONDS_TO", "citations": nodes[index + 1]["citations"]},
                {"id": f"edge-{index * 2 + 2}", "source": f"stakeholder-{index + 1}", "target": issue, "type": "RAISES", "citations": nodes[index + 1]["citations"]},
            ])
        return {"revision": 1, "ontology_version": ontology["version"], "nodes": nodes, "edges": edges, "generated_by": self.name}

    @validated("environment")
    def environment(self, simulation_id: str, graph: dict, config: dict) -> dict:
        issues = [node for node in graph["nodes"] if node["type"] == "Issue"]
        stakeholders = [node for node in graph["nodes"] if node["type"] == "Stakeholder"]
        personas = []
        names = ["Rina", "Budi", "Siti", "Arif", "Maya", "Dimas", "Nadia", "Raka", "Lestari", "Fajar"]
        for index in range(30):
            stakeholder = stakeholders[index % len(stakeholders)]
            issue = issues[index % len(issues)]
            digest = int(hashlib.sha256(f"{simulation_id}:{index}".encode()).hexdigest()[:8], 16)
            stance = ["Mendukung", "Netral", "Kritis"][digest % 3]
            personas.append({
                "id": f"persona-{index + 1}", "name": f"{names[index % len(names)]} {index + 1}",
                "group": stakeholder["label"], "stakeholder_group": stakeholder["label"], "role": "Persona sintetis",
                "profile": f"Mewakili {stakeholder['label']} dengan perhatian pada {issue['label']}.",
                "stance": stance, "concern": issue["label"], "concerns": [issue["label"]], "topics": [issue["label"]],
                "influence": 0.4 + (digest % 50) / 100, "active": True, "count": 1,
                "source_node_ids": [stakeholder["id"], issue["id"]], "citations": issue.get("citations", []),
            })
        resolved = {
            "rounds": config.get("rounds", 5), "socialization": config.get("socialization", "Sedang"),
            "response_mode": config.get("response_mode", "Responsif"),
            "channels": ["Forum warga", "Media sosial", "Rapat publik"], "influence_mode": "network_weighted",
            "events_per_round": 6, "seed": simulation_id, "assumptions": [],
            "generation_reasoning": "Konfigurasi diturunkan dari cakupan stakeholder dan isu graph.",
            "generated_by": self.name, "version": 1, "overrides": config,
        }
        return {"personas": personas, "persona_count": len(personas), "config": resolved}

    @validated("simulate")
    def simulate(self, simulation_id: str, graph: dict, personas: list[dict], config: dict) -> dict:
        events = []
        rounds = config["rounds"]
        for round_number in range(1, rounds + 1):
            for index, group in enumerate(GROUPS):
                persona = next((item for item in personas if item["group"] == group), personas[index])
                stance_index = int(hashlib.sha256(f"{simulation_id}:{round_number}:{index}".encode()).hexdigest()[:8], 16) % 3
                stance = ["Mendukung", "Netral", "Kritis"][stance_index]
                event_id = f"event-r{round_number}-{index + 1}"
                statement = f"{group} menyoroti {persona['concern'].lower()} pada putaran {round_number}."
                events.append({
                    "id": event_id, "sequence": len(events) + 1, "round": round_number,
                    "time": f"{round_number - 1:02d}:{index * 8:02d}", "channel": config["channels"][index % 3],
                    "persona_id": persona["id"], "persona": persona["name"], "persona_name": persona["name"],
                    "group": group, "type": "respons_publik", "event_type": "respons_publik",
                    "statement": statement, "content": statement, "stance": stance, "concerns": persona["concerns"],
                    "risk_narrative": "Perlu mitigasi" if stance == "Kritis" else "Terkendali",
                    "influence_source": "Graph kebijakan", "source_node_ids": persona["source_node_ids"],
                    "citations": persona.get("citations", []), "graph_revision": graph["revision"], "config_version": config["version"],
                })
        return {"id": f"run_{hashlib.sha256(simulation_id.encode()).hexdigest()[:12]}", "events": events, "event_count": len(events)}

    @validated("report")
    def report(self, project: dict, chunks: list[dict], events: list[dict]) -> dict:
        critical = [event for event in events if event["stance"] == "Kritis"]
        evidence_chunks = retrieve_chunks(f"{project['objective']} risiko akses dampak implementasi", chunks, 3)
        source_citations = [citation(chunk) for chunk in evidence_chunks]
        legacy = [f"[dok:{item['document_id']}]" for item in source_citations] or ["[event:event-r1-1]"]
        evidence = f"{len(critical)} dari {len(events)} event bersikap kritis; sumber {', '.join(legacy)} dan [event:event-r1-1]."
        return {
            "id": f"report_{hashlib.sha256((project['id'] + str(len(events))).encode()).hexdigest()[:12]}",
            "version": 1, "title": f"Laporan Simulasi {project['name']}", "generated_by": self.name,
            "sections": [
                {"id": "ringkasan", "title": "Ringkasan Eksekutif", "paragraphs": [f"Simulasi mencatat {len(events)} respons lintas kelompok. {legacy[0]}"], "citations": source_citations[:1]},
                {"id": "temuan", "title": "Temuan dan Bukti", "paragraphs": [evidence], "citations": source_citations},
                {"id": "rekomendasi", "title": "Rekomendasi", "paragraphs": ["Lakukan implementasi bertahap, buka kanal umpan balik, dan ukur akses layanan pada setiap putaran."], "citations": source_citations[:2]},
            ],
            "risks": [
                {"id": "risk-1", "title": "Resistensi kelompok terdampak", "level": "Tinggi" if len(critical) > len(events) / 3 else "Sedang", "trend": "Stabil", "evidence": evidence, "citations": source_citations},
                {"id": "risk-2", "title": "Kesenjangan implementasi", "level": "Sedang", "trend": "Meningkat", "evidence": "Isu berulang pada jejak [event:event-r1-2].", "citations": source_citations[:1]},
            ],
            "citations": source_citations,
        }

    @validated("answer")
    def answer(self, payload: dict, state: dict, chunks: list[dict]) -> dict:
        events = state["simulation"].get("events", [])
        selected = [item for item in events if not payload.get("persona_group") or item["group"] == payload["persona_group"]]
        relevant_chunks = retrieve_chunks(payload["question"], chunks, 3)
        evidence = citation(relevant_chunks[0]) if relevant_chunks else None
        citation_ids = [f"event:{selected[0]['id']}"] if selected else ["report:ringkasan"]
        return {
            "text": f"Berdasarkan {len(selected)} event relevan, '{payload['question']}' perlu ditangani bertahap dengan umpan balik terukur. [{citation_ids[0]}]",
            "citations": citation_ids,
            "evidence_citations": [evidence] if evidence else [],
        }

    @validated("interview")
    def interview(self, question: str, personas: list[dict], events: list[dict]) -> dict:
        answers = []
        for persona in personas:
            related = [event for event in events if event.get("persona_id") == persona["id"]]
            answers.append({
                "id": f"answer-{persona['id']}", "persona_id": persona["id"], "question": question,
                "answer": f"Sebagai {persona['group']}, perhatian utama saya adalah {persona['concern'].lower()}.",
                "citations": persona.get("citations", []), "event_ids": [item["id"] for item in related[:3]],
            })
        return {"answers": answers, "summary": f"Wawancara merangkum {len(answers)} perspektif persona sintetis."}

    @validated("graph_memory")
    def graph_memory(self, graph: dict, events: list[dict]) -> dict:
        critical = [event for event in events if event["stance"] == "Kritis"]
        memory_nodes = []
        memory_edges = []
        for index, event in enumerate(critical[:6]):
            node_id = f"memory-risk-{index + 1}"
            memory_nodes.append({
                "id": node_id, "label": event["concerns"][0], "type": "Risk",
                "summary": event["statement"], "memory_source": event["id"],
                "citations": event.get("citations", []), "x": 180 + index * 90, "y": 500,
            })
            source = event.get("source_node_ids", ["policy"])[0]
            memory_edges.append({
                "id": f"memory-edge-{index + 1}", "source": source, "target": node_id,
                "type": "RAISES", "summary": f"Diturunkan dari {event['id']}", "citations": event.get("citations", []),
            })
        existing_nodes = [node for node in graph["nodes"] if not node["id"].startswith("memory-risk-")]
        existing_edges = [edge for edge in graph["edges"] if not edge["id"].startswith("memory-edge-")]
        return {
            "revision": graph["revision"],
            "ontology_version": graph.get("ontology_version"),
            "generated_by": graph.get("generated_by"),
            "nodes": existing_nodes + memory_nodes,
            "edges": existing_edges + memory_edges,
            "memory_revision": graph.get("memory_revision", 0) + 1,
            "memory_event_ids": [event["id"] for event in critical],
        }


class OpenAICompatiblePolicyProvider:
    name = "openai-compatible"
    _LOCAL_FIELDS = {
        "id", "source_id", "chunk_id", "document_id", "source", "target",
        "source_node_ids", "event_ids", "memory_event_ids", "citations",
    }

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 120,
        fallback_policy: FallbackPolicy = "deterministic",
        *,
        client=None,
    ):
        if fallback_policy not in {"deterministic", "raise"}:
            raise ValueError("fallback_policy must be 'deterministic' or 'raise'")
        self.fallback_policy = fallback_policy
        self.fallback_provider = DeterministicPolicyProvider()
        self.model = model
        if client is not None:
            self.client = client
            return
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("Install backend dengan extra [llm] untuk POLICY_PROVIDER=openai") from error
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    @staticmethod
    def _local_provenance(value, fallback):
        if isinstance(value, dict) and isinstance(fallback, dict):
            result = dict(value)
            for key, fallback_value in fallback.items():
                if key in OpenAICompatiblePolicyProvider._LOCAL_FIELDS:
                    result[key] = fallback_value
                elif key in result:
                    result[key] = OpenAICompatiblePolicyProvider._local_provenance(result[key], fallback_value)
            return result
        if isinstance(value, list) and isinstance(fallback, list):
            return [
                OpenAICompatiblePolicyProvider._local_provenance(item, fallback[min(index, len(fallback) - 1)])
                if fallback else item
                for index, item in enumerate(value)
            ]
        return value

    def _json(self, operation: str, task: str, context: dict) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Anda adalah analis kebijakan Indonesia. Jawab hanya JSON lengkap yang mengikuti struktur konteks fallback. Jangan membuat ID sumber atau sitasi baru."},
                    {"role": "user", "content": json.dumps({"task": task, "context": context}, ensure_ascii=False, default=str)},
                ],
            )
        except Exception as error:
            raise ProviderTransportError(operation, str(error)) from error
        try:
            content = response.choices[0].message.content
            value = json.loads(content or "")
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderResponseError(operation, "response did not contain a valid JSON object") from error
        if not isinstance(value, dict) or not value:
            raise ProviderResponseError(operation, "response JSON object was empty")
        return value

    def _generate(self, operation: str, task: str, context: dict, fallback: dict) -> dict:
        try:
            generated = self._local_provenance(self._json(operation, task, context), fallback)
            if "generated_by" in generated:
                generated["generated_by"] = self.name
            return PROVIDER_OUTPUTS[operation].model_validate(generated, strict=True).model_dump(
                mode="python", exclude_none=True
            )
        except ValidationError as error:
            failure: ProviderError = ProviderOutputError(
                operation, "model output contract rejected payload", details=error.errors()
            )
        except ProviderError as error:
            failure = error
        if self.fallback_policy == "deterministic":
            return fallback
        raise failure

    @validated("ontology")
    def ontology(self, project: dict, chunks: list[dict]) -> dict:
        fallback = self.fallback_provider.ontology(project, chunks)
        return self._generate("ontology", "Buat ontology kebijakan", {"project": project, "chunks": chunks[:12], "fallback": fallback}, fallback)

    @validated("graph")
    def graph(self, project: dict, ontology: dict, chunks: list[dict]) -> dict:
        fallback = self.fallback_provider.graph(project, ontology, chunks)
        return self._generate("graph", "Buat graph kebijakan", {"project": project, "ontology": ontology, "chunks": chunks[:12], "fallback": fallback}, fallback)

    @validated("environment")
    def environment(self, simulation_id: str, graph: dict, config: dict) -> dict:
        fallback = self.fallback_provider.environment(simulation_id, graph, config)
        return self._generate("environment", "Buat lingkungan dan persona simulasi", {"graph": graph, "config": config, "fallback": fallback}, fallback)

    @validated("simulate")
    def simulate(self, simulation_id: str, graph: dict, personas: list[dict], config: dict) -> dict:
        fallback = self.fallback_provider.simulate(simulation_id, graph, personas, config)
        return self._generate("simulate", "Jalankan simulasi respons kebijakan", {"graph": graph, "personas": personas, "config": config, "fallback": fallback}, fallback)

    @validated("report")
    def report(self, project: dict, chunks: list[dict], events: list[dict]) -> dict:
        fallback = self.fallback_provider.report(project, chunks, events)
        return self._generate("report", "Buat laporan berdasarkan bukti", {"project": project, "chunks": chunks[:12], "events": events[:60], "fallback": fallback}, fallback)

    @validated("answer")
    def answer(self, payload: dict, state: dict, chunks: list[dict]) -> dict:
        fallback = self.fallback_provider.answer(payload, state, chunks)
        context = {"payload": payload, "state": state, "chunks": chunks[:12], "fallback": fallback}
        return self._generate("answer", "Jawab pertanyaan berdasarkan state dan bukti", context, fallback)

    @validated("interview")
    def interview(self, question: str, personas: list[dict], events: list[dict]) -> dict:
        fallback = self.fallback_provider.interview(question, personas, events)
        return self._generate("interview", "Jawab wawancara persona", {"question": question, "personas": personas, "events": events[:60], "fallback": fallback}, fallback)

    @validated("graph_memory")
    def graph_memory(self, graph: dict, events: list[dict]) -> dict:
        fallback = self.fallback_provider.graph_memory(graph, events)
        return self._generate("graph_memory", "Perbarui graph memory dari event", {"graph": graph, "events": events[:60], "fallback": fallback}, fallback)


def make_provider(settings) -> PolicyProvider:
    if settings.policy_provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY wajib diisi untuk POLICY_PROVIDER=openai")
        return OpenAICompatiblePolicyProvider(
            settings.llm_api_key, settings.llm_model, settings.llm_base_url, settings.provider_timeout_seconds
        )
    return DeterministicPolicyProvider()
