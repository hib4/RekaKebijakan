from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
import time
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


logger = logging.getLogger("rekakebijakan.provider")


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
        instruction = {
            "report": "Ringkasan laporan menekankan temuan lintas bagian",
            "persona": f"Perspektif {payload.get('persona_group') or 'persona terdampak'} menekankan pengalaman dan kekhawatiran",
            "evidence": "Jejak bukti memprioritaskan sumber dan event yang dapat diverifikasi",
            "risk": "Analisis risiko memprioritaskan tingkat dampak dan mitigasi",
            "compare": "Perbandingan menyoroti perbedaan asumsi, respons, dan hasil",
            "revision": "Usulan revisi merumuskan perubahan kebijakan yang dapat ditindaklanjuti",
        }[payload.get("tool", "report")]
        return {
            "text": f"{instruction}. Berdasarkan {len(selected)} event relevan, '{payload['question']}' perlu ditangani bertahap dengan umpan balik terukur. [{citation_ids[0]}]",
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
        max_output_tokens: int = 2500,
        client=None,
    ):
        if fallback_policy not in {"deterministic", "raise"}:
            raise ValueError("fallback_policy must be 'deterministic' or 'raise'")
        self.fallback_policy = fallback_policy
        self.fallback_provider = DeterministicPolicyProvider()
        self.model = model
        self.max_output_tokens = max_output_tokens
        if client is not None:
            self.client = client
            return
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("Install backend dengan extra [llm] untuk POLICY_PROVIDER=openai") from error
        # Durable worker retries already provide backoff and attempt tracking.
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)

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

    @staticmethod
    def _evidence(chunks: list[dict], limit: int = 6, text_limit: int = 800) -> list[dict]:
        return [
            {
                "id": item["id"],
                "document_id": item["document_id"],
                "ordinal": item["ordinal"],
                "text": item["text"][:text_limit],
            }
            for item in chunks[:limit]
        ]

    def _json(self, operation: str, task: str, context: dict) -> dict:
        serialized = json.dumps({"task": task, "context": context}, ensure_ascii=False, default=str)
        started = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_output_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Anda adalah analis kebijakan Indonesia. Jawab hanya satu objek JSON lengkap yang mengikuti "
                            "struktur dan jumlah item pada fallback. Pertahankan semua ID, referensi sumber, dan sitasi "
                            "persis seperti fallback. Jangan menambah item atau penjelasan di luar JSON. Gunakan uraian "
                            "ringkas dan spesifik berdasarkan bukti yang diberikan."
                        ),
                    },
                    {"role": "user", "content": serialized},
                ],
            )
        except Exception as error:
            logger.warning(
                "llm_request_failed operation=%s model=%s duration_ms=%d input_chars=%d error_type=%s",
                operation, self.model, int((time.monotonic() - started) * 1000), len(serialized), type(error).__name__,
            )
            raise ProviderTransportError(operation, str(error)) from error
        logger.info(
            "llm_request_completed operation=%s model=%s duration_ms=%d input_chars=%d",
            operation, self.model, int((time.monotonic() - started) * 1000), len(serialized),
        )
        try:
            content = response.choices[0].message.content
            text = (content or "").strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
            value = json.loads(text)
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
            logger.warning(
                "llm_fallback operation=%s category=%s message=%s",
                operation, failure.category, failure,
            )
            return fallback
        raise failure

    def _merge_ontology_refinements(self, generated: dict, fallback: dict) -> dict:
        result = dict(fallback)
        summary = generated.get("analysis_summary")
        if isinstance(summary, str) and summary.strip():
            result["analysis_summary"] = summary.strip()

        for key, fields in (
            ("entity_types", ("name", "description")),
            ("relation_types", ("name",)),
        ):
            updates = generated.get(key)
            if not isinstance(updates, list):
                continue
            merged = []
            for index, local in enumerate(fallback[key]):
                item = dict(local)
                update = updates[index] if index < len(updates) else None
                if isinstance(update, dict):
                    for field in fields:
                        value = update.get(field)
                        if isinstance(value, str) and value.strip():
                            item[field] = value.strip()
                merged.append(item)
            result[key] = merged

        result["generated_by"] = self.name
        return PROVIDER_OUTPUTS["ontology"].model_validate(result, strict=True).model_dump(
            mode="python", exclude_none=True
        )

    @validated("ontology")
    def ontology(self, project: dict, chunks: list[dict]) -> dict:
        fallback = self.fallback_provider.ontology(project, chunks)
        evidence = retrieve_chunks(project["objective"], chunks, 6)
        try:
            generated = self._json(
                "ontology",
                (
                    "Perjelas ringkasan dan label ontology berdasarkan bukti. Kembalikan objek JSON dengan key "
                    "analysis_summary, entity_types, dan relation_types. entity_types harus berisi tepat satu item "
                    "untuk setiap input dengan hanya key name dan description. relation_types harus berisi tepat "
                    "satu item untuk setiap input dengan hanya key name. Jangan mengembalikan citations, source_types, "
                    "target_types, version, atau generated_by."
                ),
                {
                    "project": project,
                    "chunks": self._evidence(evidence),
                    "entity_types": [
                        {key: item[key] for key in ("name", "description")}
                        for item in fallback["entity_types"]
                    ],
                    "relation_types": [{"name": item["name"]} for item in fallback["relation_types"]],
                },
            )
            return self._merge_ontology_refinements(generated, fallback)
        except ValidationError as error:
            failure: ProviderError = ProviderOutputError(
                "ontology", "model output contract rejected payload", details=error.errors()
            )
        except ProviderError as error:
            failure = error
        if self.fallback_policy == "deterministic":
            logger.warning(
                "llm_fallback operation=%s category=%s message=%s",
                "ontology", failure.category, failure,
            )
            return fallback
        raise failure

    @validated("graph")
    def graph(self, project: dict, ontology: dict, chunks: list[dict]) -> dict:
        fallback = self.fallback_provider.graph(project, ontology, chunks)
        compact_nodes = [
            {key: node.get(key) for key in ("id", "label", "type", "summary")}
            for node in fallback["nodes"]
        ]
        generated = self._json(
            "graph",
            (
                "Perjelas label dan ringkasan node graph berdasarkan ontology dan bukti. Kembalikan objek "
                "dengan key nodes yang berisi tepat satu item untuk setiap ID input; setiap item hanya memiliki "
                "id, label, dan summary. Jangan membuat atau menghapus ID."
            ),
            {
                "project": project,
                "ontology_summary": ontology.get("analysis_summary", ""),
                "nodes": compact_nodes,
                "chunks": self._evidence(retrieve_chunks(project["objective"], chunks, 4), 4, 600),
            },
        )
        updates = generated.get("nodes")
        if not isinstance(updates, list):
            raise ProviderResponseError("graph", "response JSON must contain a nodes array")
        by_id = {
            item.get("id"): item
            for item in updates
            if isinstance(item, dict) and item.get("id")
        }
        expected_ids = {node["id"] for node in fallback["nodes"]}
        if set(by_id) != expected_ids:
            raise ProviderResponseError("graph", "response nodes must preserve every input node ID")
        result = dict(fallback)
        result["generated_by"] = self.name
        result["nodes"] = [
            node | {
                "label": str(by_id[node["id"]].get("label") or node["label"]),
                "summary": str(by_id[node["id"]].get("summary") or node["summary"]),
            }
            for node in fallback["nodes"]
        ]
        return PROVIDER_OUTPUTS["graph"].model_validate(result, strict=True).model_dump(
            mode="python", exclude_none=True
        )

    @validated("environment")
    def environment(self, simulation_id: str, graph: dict, config: dict) -> dict:
        fallback = self.fallback_provider.environment(simulation_id, graph, config)
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}
        persona_updates = {}

        try:
            generated_config = self._json(
                "environment",
                (
                    "Perjelas asumsi dan alasan konfigurasi lingkungan simulasi. Kembalikan objek dengan key "
                    "assumptions berupa array dan generation_reasoning berupa string."
                ),
                {
                    "requested_config": config,
                    "resolved_config": {
                        key: fallback["config"][key]
                        for key in ("rounds", "socialization", "response_mode", "events_per_round")
                    },
                    "graph_nodes": [
                        {key: node.get(key) for key in ("id", "label", "type", "summary")}
                        for node in graph["nodes"]
                    ],
                },
            )
            assumptions = generated_config.get("assumptions")
            reasoning = generated_config.get("generation_reasoning")
            if not isinstance(assumptions, list) or not isinstance(reasoning, str) or not reasoning.strip():
                raise ProviderResponseError(
                    "environment", "config response must contain assumptions and generation_reasoning"
                )

            for start in range(0, len(fallback["personas"]), 10):
                personas = fallback["personas"][start:start + 10]
                node_ids = {
                    node_id
                    for persona in personas
                    for node_id in persona["source_node_ids"]
                }
                generated = self._json(
                    "environment",
                    (
                        "Perjelas persona sintetis berdasarkan node graph. Kembalikan objek dengan key personas "
                        "yang berisi tepat satu item untuk setiap ID input. Setiap item hanya memiliki id, name, "
                        "role, profile, dan stance. Jangan membuat, menghapus, atau mengubah ID."
                    ),
                    {
                        "requested_config": config,
                        "personas": [
                            {
                                key: persona.get(key)
                                for key in ("id", "name", "group", "role", "profile", "stance", "concern")
                            }
                            for persona in personas
                        ],
                        "graph_nodes": [
                            {
                                key: node.get(key)
                                for key in ("id", "label", "type", "summary")
                            }
                            for node_id in sorted(node_ids)
                            if (node := nodes_by_id.get(node_id))
                        ],
                    },
                )
                updates = generated.get("personas")
                if not isinstance(updates, list) or any(not isinstance(item, dict) for item in updates):
                    raise ProviderResponseError("environment", "response JSON must contain a personas array")
                update_ids = [item.get("id") for item in updates]
                expected_ids = {persona["id"] for persona in personas}
                if (
                    any(not isinstance(persona_id, str) or not persona_id for persona_id in update_ids)
                    or len(update_ids) != len(set(update_ids))
                    or set(update_ids) != expected_ids
                ):
                    raise ProviderResponseError(
                        "environment", "response personas must preserve every input persona ID"
                    )
                persona_updates.update({item["id"]: item for item in updates})

            result = dict(fallback)
            result["config"] = fallback["config"] | {
                "assumptions": assumptions,
                "generation_reasoning": reasoning.strip(),
                "generated_by": self.name,
            }
            result["personas"] = [
                persona | {
                    "name": str(persona_updates[persona["id"]].get("name") or persona["name"]),
                    "role": str(persona_updates[persona["id"]].get("role") or persona["role"]),
                    "profile": str(persona_updates[persona["id"]].get("profile") or persona["profile"]),
                    "stance": str(persona_updates[persona["id"]].get("stance") or persona["stance"]),
                }
                for persona in fallback["personas"]
            ]
            return PROVIDER_OUTPUTS["environment"].model_validate(result, strict=True).model_dump(
                mode="python", exclude_none=True
            )
        except ValidationError as error:
            failure: ProviderError = ProviderOutputError(
                "environment", "model output contract rejected payload", details=error.errors()
            )
        except ProviderError as error:
            failure = error
        if self.fallback_policy == "deterministic":
            logger.warning(
                "llm_fallback operation=environment category=%s message=%s",
                failure.category, failure,
            )
            return fallback
        raise failure

    @validated("simulate")
    def simulate(self, simulation_id: str, graph: dict, personas: list[dict], config: dict) -> dict:
        fallback = self.fallback_provider.simulate(simulation_id, graph, personas, config)
        personas_by_id = {persona["id"]: persona for persona in personas}
        nodes_by_id = {node["id"]: node for node in graph["nodes"]}
        rounds = sorted({event["round"] for event in fallback["events"]})
        refined_by_id = {}

        try:
            for round_number in rounds:
                events = [event for event in fallback["events"] if event["round"] == round_number]
                persona_ids = {event["persona_id"] for event in events}
                node_ids = {
                    node_id
                    for event in events
                    for node_id in event["source_node_ids"]
                }
                generated = self._json(
                    "simulate",
                    (
                        "Perjelas respons pada satu putaran simulasi. Kembalikan objek dengan key events yang "
                        "berisi tepat satu item untuk setiap ID input. Setiap item hanya memiliki id, statement, "
                        "stance, dan risk_narrative. Jangan membuat, menghapus, atau mengubah ID."
                    ),
                    {
                        "round": round_number,
                        "response_mode": config.get("response_mode"),
                        "socialization": config.get("socialization"),
                        "events": [
                            {
                                "id": event["id"],
                                "persona_id": event["persona_id"],
                                "group": event["group"],
                                "concerns": event["concerns"],
                                "statement": event["statement"],
                                "stance": event["stance"],
                                "risk_narrative": event["risk_narrative"],
                            }
                            for event in events
                        ],
                        "personas": [
                            {
                                key: persona.get(key)
                                for key in ("id", "name", "group", "profile", "stance", "concern")
                            }
                            for persona_id in sorted(persona_ids)
                            if (persona := personas_by_id.get(persona_id))
                        ],
                        "graph_nodes": [
                            {
                                key: node.get(key)
                                for key in ("id", "label", "type", "summary")
                            }
                            for node_id in sorted(node_ids)
                            if (node := nodes_by_id.get(node_id))
                        ],
                    },
                )
                updates = generated.get("events")
                if not isinstance(updates, list) or any(not isinstance(item, dict) for item in updates):
                    raise ProviderResponseError("simulate", "response JSON must contain an events array")
                update_ids = [item.get("id") for item in updates]
                expected_ids = {event["id"] for event in events}
                if (
                    any(not isinstance(event_id, str) or not event_id for event_id in update_ids)
                    or len(update_ids) != len(set(update_ids))
                    or set(update_ids) != expected_ids
                ):
                    raise ProviderResponseError("simulate", "response events must preserve every input event ID")
                refined_by_id.update({item["id"]: item for item in updates})

            result = dict(fallback)
            result["events"] = []
            for event in fallback["events"]:
                update = refined_by_id[event["id"]]
                refined = event | {
                    "statement": update.get("statement") or event["statement"],
                    "stance": update.get("stance") or event["stance"],
                    "risk_narrative": update.get("risk_narrative") or event["risk_narrative"],
                }
                refined["content"] = refined["statement"]
                result["events"].append(refined)
            return PROVIDER_OUTPUTS["simulate"].model_validate(result, strict=True).model_dump(
                mode="python", exclude_none=True
            )
        except ValidationError as error:
            failure: ProviderError = ProviderOutputError(
                "simulate", "model output contract rejected payload", details=error.errors()
            )
        except ProviderError as error:
            failure = error
        if self.fallback_policy == "deterministic":
            logger.warning(
                "llm_fallback operation=simulate category=%s message=%s",
                failure.category, failure,
            )
            return fallback
        raise failure

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
        memory_nodes = [node for node in fallback["nodes"] if node.get("memory_source")]
        if not memory_nodes:
            return fallback
        events_by_id = {event["id"]: event for event in events}
        try:
            generated = self._json(
                "graph_memory",
                (
                    "Perjelas label dan ringkasan node memory berdasarkan event simulasi. Kembalikan objek dengan "
                    "key nodes yang berisi tepat satu item untuk setiap ID input; setiap item hanya memiliki id, "
                    "label, dan summary. Jangan membuat, menghapus, atau mengubah ID."
                ),
                {
                    "nodes": [
                        {key: node.get(key) for key in ("id", "label", "summary", "memory_source")}
                        for node in memory_nodes
                    ],
                    "events": [
                        {
                            key: event.get(key)
                            for key in ("id", "group", "statement", "stance", "concerns")
                        }
                        for node in memory_nodes
                        if (event := events_by_id.get(node["memory_source"]))
                    ],
                },
            )
            updates = generated.get("nodes")
            if not isinstance(updates, list) or any(not isinstance(item, dict) for item in updates):
                raise ProviderResponseError("graph_memory", "response JSON must contain a nodes array")
            update_ids = [item.get("id") for item in updates]
            expected_ids = {node["id"] for node in memory_nodes}
            if (
                any(not isinstance(node_id, str) or not node_id for node_id in update_ids)
                or len(update_ids) != len(set(update_ids))
                or set(update_ids) != expected_ids
            ):
                raise ProviderResponseError("graph_memory", "response nodes must preserve every input memory node ID")
            by_id = {item["id"]: item for item in updates}
            result = dict(fallback)
            result["nodes"] = [
                node | {
                    "label": str(by_id[node["id"]].get("label") or node["label"]),
                    "summary": str(by_id[node["id"]].get("summary") or node["summary"]),
                }
                if node["id"] in by_id else node
                for node in fallback["nodes"]
            ]
            return PROVIDER_OUTPUTS["graph_memory"].model_validate(result, strict=True).model_dump(
                mode="python", exclude_none=True
            )
        except ValidationError as error:
            failure: ProviderError = ProviderOutputError(
                "graph_memory", "model output contract rejected payload", details=error.errors()
            )
        except ProviderError as error:
            failure = error
        if self.fallback_policy == "deterministic":
            logger.warning(
                "llm_fallback operation=graph_memory category=%s message=%s",
                failure.category, failure,
            )
            return fallback
        raise failure


def make_provider(settings) -> PolicyProvider:
    if settings.policy_provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY wajib diisi untuk POLICY_PROVIDER=openai")
        return OpenAICompatiblePolicyProvider(
            settings.llm_api_key, settings.llm_model, settings.llm_base_url,
            settings.provider_timeout_seconds, settings.llm_fallback_policy,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    return DeterministicPolicyProvider()
