from __future__ import annotations

from typing import Any


OUTPUT_LANGUAGES = {
    "id": "Bahasa Indonesia",
    "en": "English",
}


def apply_output_language(agent_graph: Any, language: str = "id") -> None:
    """Constrain agent prose without changing OASIS tool names or schemas."""
    output_language = OUTPUT_LANGUAGES.get(language, OUTPUT_LANGUAGES["id"])
    for _, agent in agent_graph.get_agents():
        agent.output_language = output_language
