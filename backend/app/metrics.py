from __future__ import annotations

import re
import threading
from collections import Counter


identifier_path = re.compile(r"/(?P<resource>projects|scenarios|simulations|jobs)/[^/]+")


def route_label(path: str) -> str:
    return identifier_path.sub(lambda match: f"/{match.group('resource')}/{{id}}", path)


class MetricsRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests: Counter[tuple[str, str, int]] = Counter()
        self.duration_seconds: Counter[tuple[str, str]] = Counter()

    def observe_request(self, method: str, path: str, status: int, duration_seconds: float) -> None:
        route = route_label(path)
        with self.lock:
            self.requests[(method, route, status)] += 1
            self.duration_seconds[(method, route)] += duration_seconds

    @staticmethod
    def labels(**values: str | int) -> str:
        encoded = ",".join(f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"' for key, value in values.items())
        return "{" + encoded + "}"

    def render(self, queue: dict[str, int | float]) -> str:
        with self.lock:
            requests = dict(self.requests)
            durations = dict(self.duration_seconds)
        lines = [
            "# HELP rekakebijakan_http_requests_total HTTP responses by route and status.",
            "# TYPE rekakebijakan_http_requests_total counter",
        ]
        for (method, route, status), value in sorted(requests.items()):
            lines.append(f"rekakebijakan_http_requests_total{self.labels(method=method, route=route, status=status)} {value}")
        lines.extend([
            "# HELP rekakebijakan_http_request_duration_seconds_sum Total HTTP request duration.",
            "# TYPE rekakebijakan_http_request_duration_seconds_sum counter",
        ])
        for (method, route), value in sorted(durations.items()):
            lines.append(f"rekakebijakan_http_request_duration_seconds_sum{self.labels(method=method, route=route)} {value:.6f}")
        lines.extend([
            "# HELP rekakebijakan_jobs Current durable job count by state.",
            "# TYPE rekakebijakan_jobs gauge",
        ])
        for status in ("queued", "running", "paused", "failed", "dead_letter"):
            lines.append(f"rekakebijakan_jobs{self.labels(status=status)} {queue.get(status, 0)}")
        lines.extend([
            "# HELP rekakebijakan_oldest_queued_job_age_seconds Age of the oldest queued job.",
            "# TYPE rekakebijakan_oldest_queued_job_age_seconds gauge",
            f"rekakebijakan_oldest_queued_job_age_seconds {queue.get('oldest_queued_age_seconds', 0):.3f}",
        ])
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()
