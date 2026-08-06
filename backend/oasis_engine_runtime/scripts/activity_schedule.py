from __future__ import annotations

import random
from typing import Any


def select_active_agent_ids(
    config: dict[str, Any],
    current_hour: int,
    rng: Any = random,
) -> list[int]:
    """Select at least one configured agent for every simulated round."""
    time_config = config.get("time_config", {})
    agent_configs = config.get("agent_configs", [])
    if not agent_configs:
        return []

    base_min = time_config.get("agents_per_hour_min", 5)
    base_max = time_config.get("agents_per_hour_max", 20)
    peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
    off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])
    if current_hour in peak_hours:
        multiplier = time_config.get("peak_activity_multiplier", 1.5)
    elif current_hour in off_peak_hours:
        multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
    else:
        multiplier = 1.0

    target_count = max(1, int(rng.uniform(base_min, base_max) * multiplier))
    all_ids = [int(item.get("agent_id", 0)) for item in agent_configs]
    scheduled = [
        int(item.get("agent_id", 0))
        for item in agent_configs
        if current_hour in item.get("active_hours", list(range(8, 23)))
    ]
    eligible = scheduled or all_ids
    active = [
        int(item.get("agent_id", 0))
        for item in agent_configs
        if int(item.get("agent_id", 0)) in eligible
        and rng.random() < item.get("activity_level", 0.5)
    ]
    pool = active or eligible
    return rng.sample(pool, min(target_count, len(pool)))
