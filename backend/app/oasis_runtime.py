from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import httpx

from .provider_errors import ProviderResponseError, ProviderTransportError


class OasisRuntimeClient:
    name = "oasis-runtime"

    def __init__(self, base_url: str, service_token: str, timeout: float = 3600):
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-Service-Token": service_token},
            timeout=timeout,
        )

    def close(self) -> None:
        self.client.close()

    def _request(self, operation: str, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderTransportError(operation, str(error)) from error
        if not isinstance(payload, dict) or not payload.get("success") or not isinstance(payload.get("data"), dict):
            message = payload.get("error", "invalid OASIS runtime response") if isinstance(payload, dict) else "invalid OASIS runtime response"
            raise ProviderResponseError(operation, str(message))
        return payload["data"]

    def sync_graph(self, simulation_id: str, state: dict, chunks: list[dict]) -> dict:
        return self._request("environment", "POST", "/api/bridge/graph/sync", json={
            "local_simulation_id": simulation_id,
            "project_name": state["project"]["name"],
            "simulation_requirement": state["project"]["objective"],
            "ontology": state["ontology"],
            "chunks": chunks,
        })

    def prepare_environment(self, mapping: dict, state: dict, config: dict) -> dict:
        return self._request("environment", "POST", "/api/bridge/environment/prepare", json={
            "external_project_id": mapping["external_project_id"],
            "external_simulation_id": mapping.get("external_simulation_id"),
            "graph_id": mapping["zep_graph_id"],
            "simulation_requirement": state["project"]["objective"],
            "entity_types": config.get("entity_types"),
            "use_llm_for_profiles": config.get("use_llm_for_profiles", True),
            "parallel_profile_count": config.get("parallel_profile_count", 5),
        })

    def start_simulation(self, mapping: dict, config: dict) -> dict:
        return self._request("simulate", "POST", "/api/bridge/simulation/start", json={
            "simulation_id": mapping["external_simulation_id"],
            "graph_id": mapping["zep_graph_id"],
            "max_rounds": config.get("max_rounds", 40),
            "enable_graph_memory_update": config.get("enable_graph_memory_update", True),
            "force": config.get("force", False),
        })

    def simulation_snapshot(self, external_simulation_id: str) -> dict:
        return self._request(
            "simulate", "GET", f"/api/bridge/simulation/{external_simulation_id}/snapshot"
        )

    def stop_simulation(self, external_simulation_id: str) -> dict:
        return self._request(
            "simulate", "POST", f"/api/bridge/simulation/{external_simulation_id}/stop"
        )


def profile_citations(profile: dict, graph: dict) -> tuple[list[str], list[dict]]:
    labels = {
        str(profile.get("name", "")).casefold(),
        str(profile.get("source_entity_type", "")).casefold(),
    }
    nodes = [
        node for node in graph.get("nodes", [])
        if str(node.get("label", "")).casefold() in labels
        or str(node.get("type", "")).casefold() in labels
    ]
    if not nodes:
        nodes = [node for node in graph.get("nodes", []) if node.get("citations")][:1]
    return [node["id"] for node in nodes], [citation for node in nodes for citation in node.get("citations", [])]


def normalize_environment(simulation_id: str, graph: dict, prepared: dict, requested: dict) -> dict:
    raw_config = prepared["config"] or {}
    agent_configs = {
        int(item.get("agent_id", index)): item
        for index, item in enumerate(raw_config.get("agent_configs", []))
    }
    personas = []
    for index, profile in enumerate(prepared.get("profiles", [])):
        agent_id = int(profile.get("user_id", index))
        behavior = agent_configs.get(agent_id, {})
        source_node_ids, citations = profile_citations(profile, graph)
        topics = profile.get("interested_topics") or []
        if isinstance(topics, str):
            topics = [item.strip() for item in topics.split(",") if item.strip()]
        concern = topics[0] if topics else profile.get("bio") or "Respons kebijakan"
        group = profile.get("source_entity_type") or profile.get("profession") or "Stakeholder"
        personas.append({
            "id": f"oasis-{agent_id}",
            "name": profile.get("name") or profile.get("username") or f"Agent {agent_id}",
            "group": str(group), "stakeholder_group": str(group),
            "role": profile.get("profession") or "OASIS agent",
            "profile": profile.get("persona") or profile.get("bio") or str(group),
            "stance": str(behavior.get("stance", "neutral")),
            "concern": str(concern), "concerns": [str(concern)], "topics": [str(item) for item in topics],
            "influence": float(behavior.get("influence_weight", 0.5)),
            "active": True, "count": 1,
            "source_node_ids": source_node_ids, "citations": citations,
        })
    time_config = raw_config.get("time_config", {})
    hours = int(time_config.get("total_simulation_hours", 40) or 40)
    minutes = int(time_config.get("minutes_per_round", 60) or 60)
    natural_rounds = max(1, hours * 60 // max(1, minutes))
    rounds = min(natural_rounds, int(requested.get("max_rounds", natural_rounds)))
    return {
        "personas": personas,
        "persona_count": len(personas),
        "config": {
            "rounds": rounds,
            "socialization": "OASIS activity model",
            "response_mode": "LLMAction",
            "channels": ["twitter", "reddit"],
            "influence_mode": "oasis_agent_config",
            "events_per_round": max(1, len(personas)),
            "seed": simulation_id,
            "assumptions": raw_config.get("assumptions", []),
            "generation_reasoning": raw_config.get("generation_reasoning", "Generated by the OASIS runtime"),
            "generated_by": "oasis-runtime",
            "version": 1,
            "overrides": requested,
            "platforms": ["twitter", "reddit"],
            "total_simulation_hours": hours,
            "minutes_per_round": minutes,
            "max_rounds": rounds,
            "raw_config": raw_config,
        },
    }


def normalize_action(action: dict, sequence: int, personas: list[dict], graph_revision: int, config_version: int) -> dict:
    agent_id = int(action.get("agent_id", -1))
    persona = next((item for item in personas if item["id"] == f"oasis-{agent_id}"), None)
    name = action.get("agent_name") or (persona or {}).get("name") or f"Agent {agent_id}"
    args = action.get("action_args") or {}
    action_type = str(action.get("action_type", "ACTION"))
    content = (
        args.get("content") or args.get("quote_content") or args.get("query")
        or f"{name} melakukan {action_type.lower().replace('_', ' ')}."
    )
    stance = (persona or {}).get("stance", "neutral")
    occurred = str(action.get("timestamp") or datetime.now(timezone.utc).isoformat())
    digest = hashlib.sha256(
        f"{action.get('platform')}:{action.get('round_num')}:{agent_id}:{sequence}:{occurred}".encode()
    ).hexdigest()[:16]
    return {
        "id": f"oasis-event-{digest}", "sequence": sequence,
        "round": max(1, int(action.get("round_num", 1))), "time": occurred,
        "channel": str(action.get("platform", "oasis")),
        "persona_id": (persona or {}).get("id", f"oasis-{agent_id}"),
        "persona": str(name), "persona_name": str(name),
        "group": (persona or {}).get("group", "Stakeholder"),
        "type": action_type, "event_type": action_type,
        "statement": str(content), "content": str(content), "stance": str(stance),
        "concerns": (persona or {}).get("concerns", []),
        "risk_narrative": "Interaksi platform OASIS",
        "influence_source": "OASIS dual-platform simulation",
        "source_node_ids": (persona or {}).get("source_node_ids", []),
        "citations": (persona or {}).get("citations", []),
        "graph_revision": graph_revision, "config_version": config_version,
        "platform": action.get("platform"), "action_args": args, "success": bool(action.get("success", True)),
    }


def source_identity(action: dict, index: int) -> str:
    raw = f"{action.get('round_num')}:{action.get('agent_id')}:{action.get('action_type')}:{action.get('timestamp')}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()
