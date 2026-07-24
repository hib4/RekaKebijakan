from app import engine


def test_generation_is_deterministic_and_has_30_personas():
    first = engine.graph("seed", "Kebijakan", ["policy.md"])
    second = engine.graph("seed", "Kebijakan", ["policy.md"])
    assert first == second
    environment = engine.environment("seed", {"rounds": 8, "socialization": "Sedang", "response_mode": "Responsif"})
    assert len(environment["personas"]) == 30
    assert environment["config"]["rounds"] == 8
    assert engine.events("seed", 3) == engine.events("seed", 3)
    assert len(engine.events("seed", 3)) == 18
