from app.oasis_runtime import normalize_action, normalize_environment, source_identity


def graph():
    citation = {
        "source_type": "document_chunk", "source_id": "chunk-1", "chunk_id": "chunk-1",
        "document_id": "doc-1", "locator": {"ordinal": 0}, "quote": "Bukti kebijakan",
    }
    return {
        "revision": 2,
        "nodes": [{"id": "stakeholder-1", "label": "Rina", "type": "Stakeholder", "citations": [citation]}],
        "edges": [],
    }


def test_oasis_environment_preserves_local_evidence():
    prepared = {
        "profiles": [{
            "user_id": 7, "name": "Rina", "username": "rina", "bio": "Warga",
            "persona": "Warga yang aktif", "profession": "Warga", "interested_topics": ["Akses"],
            "source_entity_type": "Stakeholder",
        }],
        "config": {
            "time_config": {"total_simulation_hours": 72, "minutes_per_round": 60},
            "agent_configs": [{"agent_id": 7, "stance": "critical", "influence_weight": 0.8}],
            "generation_reasoning": "Konfigurasi OASIS",
        },
    }

    environment = normalize_environment("sim-1", graph(), prepared, {"max_rounds": 40})

    assert environment["persona_count"] == 1
    assert environment["config"]["rounds"] == 40
    assert environment["config"]["platforms"] == ["twitter", "reddit"]
    assert environment["personas"][0]["id"] == "oasis-7"
    assert environment["personas"][0]["source_node_ids"] == ["stakeholder-1"]
    assert environment["personas"][0]["citations"][0]["source_id"] == "chunk-1"


def test_oasis_action_normalization_is_stable_and_cited():
    environment = normalize_environment("sim-1", graph(), {
        "profiles": [{
            "user_id": 7, "name": "Rina", "bio": "Warga", "persona": "Warga aktif",
            "profession": "Warga", "interested_topics": ["Akses"], "source_entity_type": "Stakeholder",
        }],
        "config": {"agent_configs": [{"agent_id": 7}], "time_config": {}},
    }, {})
    action = {
        "round_num": 3, "timestamp": "2026-07-27T10:00:00+00:00", "platform": "twitter",
        "agent_id": 7, "agent_name": "Rina", "action_type": "CREATE_POST",
        "action_args": {"content": "Akses perlu diperbaiki"}, "success": True,
    }

    event = normalize_action(action, 1, environment["personas"], 2, 1)

    assert event["channel"] == "twitter"
    assert event["event_type"] == "CREATE_POST"
    assert event["statement"] == "Akses perlu diperbaiki"
    assert event["citations"][0]["source_id"] == "chunk-1"
    assert source_identity(action, 1) == source_identity(action, 1)
