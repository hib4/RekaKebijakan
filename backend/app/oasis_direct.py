from __future__ import annotations

import hashlib
import csv
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .provider_errors import ProviderResponseError, ProviderTransportError


class DirectOasisEngine:
    """Runs RekaKebijakan's bundled CAMEL/OASIS engine on the worker host."""

    name = "oasis-direct"

    def __init__(self, runtime_dir: Path, data_dir: Path, timeout: float = 3600):
        self.runtime_dir = runtime_dir.resolve()
        self.data_dir = data_dir.resolve()
        self.timeout = timeout
        self.bridge = Path(__file__).with_name("oasis_direct_bridge.py")
        runtime_python = self.runtime_dir / ".venv" / "bin" / "python"
        self.runtime_python = runtime_python if runtime_python.exists() else Path(sys.executable)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        return None

    def _environment(self) -> dict[str, str]:
        return os.environ.copy() | {
            "REKAKEBIJAKAN_OASIS_RUNTIME_PATH": str(self.runtime_dir),
            "OASIS_DATA_DIR": str(self.data_dir),
            "LLM_MODEL_NAME": os.getenv("LLM_MODEL", os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONWARNINGS": "ignore:invalid escape sequence:SyntaxWarning",
        }

    def _call(self, operation: str, payload: dict, timeout: float | None = None) -> dict:
        operation_timeout = timeout if timeout is not None else self.timeout
        started_at = time.monotonic()
        try:
            result = subprocess.run(
                [str(self.runtime_python), str(self.bridge), operation],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                env=self._environment(),
                timeout=operation_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            diagnostics = error.stderr or error.stdout or ""
            if isinstance(diagnostics, bytes):
                diagnostics = diagnostics.decode("utf-8", errors="replace")
            detail = f"timed out after {operation_timeout:g}s"
            if diagnostics.strip():
                detail = f"{detail}; last output: {diagnostics.strip()[-1000:]}"
            raise ProviderTransportError(operation, detail) from error
        except OSError as error:
            raise ProviderTransportError(operation, str(error)) from error
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or f"bridge exited {result.returncode}"
            raise ProviderTransportError(operation, message)
        if result.stderr.strip():
            print(result.stderr.rstrip(), file=sys.stderr)
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ProviderResponseError(operation, "invalid direct OASIS response") from error
        if not isinstance(response, dict) or not response.get("success"):
            raise ProviderResponseError(operation, str(response.get("error", "direct OASIS operation failed")))
        elapsed = time.monotonic() - started_at
        if elapsed > 10:
            print(f"OASIS {operation} completed in {elapsed:.1f}s", file=sys.stderr)
        return response.get("data") or {}

    def _call_stream(
        self, operation: str, payload: dict, callback: Callable[[dict], None],
        timeout: float | None = None,
    ) -> dict:
        operation_timeout = timeout if timeout is not None else self.timeout
        process = subprocess.Popen(
            [str(self.runtime_python), str(self.bridge), operation],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=self._environment(),
        )
        messages: queue.Queue[str | None] = queue.Queue()
        diagnostics: list[str] = []

        def read_stdout() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                messages.put(line)
            messages.put(None)

        def read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                diagnostics.append(line.rstrip())
                if len(diagnostics) > 100:
                    diagnostics.pop(0)
                print(line.rstrip(), file=sys.stderr)

        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        assert process.stdin is not None
        process.stdin.write(json.dumps(payload, ensure_ascii=False))
        process.stdin.close()
        deadline = time.monotonic() + operation_timeout
        result: dict | None = None
        stream_closed = False
        while not stream_closed:
            if time.monotonic() >= deadline:
                process.kill()
                raise ProviderTransportError(operation, f"timed out after {operation_timeout:g}s")
            try:
                line = messages.get(timeout=0.25)
            except queue.Empty:
                if process.poll() is not None and not stdout_thread.is_alive():
                    break
                continue
            if line is None:
                stream_closed = True
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                process.kill()
                raise ProviderResponseError(operation, "invalid streaming response") from error
            kind = message.get("kind")
            if kind == "result":
                result = message.get("data") or {}
            elif kind == "error":
                process.wait(timeout=5)
                raise ProviderResponseError(operation, str(message.get("error", "streaming operation failed")))
            else:
                callback(message)
        remaining = max(0.1, deadline - time.monotonic())
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            process.kill()
            raise ProviderTransportError(operation, f"timed out after {operation_timeout:g}s") from error
        stderr_thread.join(timeout=1)
        if return_code:
            raise ProviderTransportError(
                operation, diagnostics[-1] if diagnostics else f"bridge exited {return_code}",
            )
        if result is None:
            raise ProviderResponseError(operation, "stream ended without a result")
        return result

    def sync_graph(
        self, simulation_id: str, state: dict, chunks: list[dict], *, graph_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None, checkpoint: dict | None = None,
    ) -> dict:
        payload = {
            "simulation_id": simulation_id,
            "project_name": state["project"]["name"],
            "simulation_requirement": state["project"]["objective"],
            "ontology": state["ontology"],
            "chunks": chunks,
            "language": state.get("project", {}).get("language", "id"),
            "graph_id": graph_id,
            "graph_exists": bool(checkpoint) and (checkpoint or {}).get("status") not in {
                "creating", "graph-creating", "graph-reserved",
            },
            "batch_id": (checkpoint or {}).get("batch_id"),
            "operation_id": (checkpoint or {}).get("operation_id"),
        }
        timeout = max(self.timeout, 660)
        if progress_callback:
            return self._call_stream("sync-graph-stream", payload, progress_callback, timeout=timeout)
        return self._call("sync-graph", payload, timeout=timeout)

    def prepare_environment(self, mapping: dict, state: dict, config: dict) -> dict:
        prepare_timeout = float(os.getenv("OASIS_PREPARE_TIMEOUT_SECONDS", "900"))
        return self._call("prepare", {
            "simulation_id": state["id"],
            "project_id": state["project"]["id"],
            "graph_id": mapping["zep_graph_id"],
            "simulation_requirement": state["project"]["objective"],
            "document_text": "\n\n".join(item.get("text", "") for item in config.pop("_chunks", [])),
            "config": config,
            "language": state.get("project", {}).get("language", "id"),
        }, timeout=max(self.timeout, prepare_timeout))

    def start_simulation(self, mapping: dict, config: dict) -> dict:
        simulation_id = mapping["external_simulation_id"]
        simulation_dir = self.data_dir / simulation_id
        config_path = simulation_dir / "simulation_config.json"
        if not config_path.exists():
            raise ProviderResponseError("simulate", "OASIS configuration does not exist")
        status_path = simulation_dir / "direct_runtime.json"
        old = self._read_json(status_path)
        if old.get("runner_status") == "running" and self._pid_alive(old.get("pid")):
            return old
        if self._pid_alive(old.get("pid")):
            self.stop_simulation(simulation_id)
        for relative in ("twitter/actions.jsonl", "reddit/actions.jsonl", "env_status.json"):
            path = simulation_dir / relative
            if path.exists():
                path.unlink()
        command = [
            str(self.runtime_python),
            str(self.runtime_dir / "scripts" / "run_parallel_simulation.py"),
            "--config", str(config_path),
            "--max-rounds", str(int(config.get("rounds", config.get("max_rounds", 10)))),
            "--step-timeout-seconds", str(float(config.get("step_timeout_seconds") or 120)),
            "--step-cleanup-grace-seconds", str(float(config.get("step_cleanup_grace_seconds") or 5)),
            "--oasis-concurrency", str(int(config.get("oasis_concurrency") or 2)),
            "--language", str(config.get("language") or "id"),
        ]
        log = (simulation_dir / "simulation.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            command,
            cwd=simulation_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=self._environment(),
            start_new_session=True,
        )
        log.close()
        runtime = {
            "runner_status": "running", "pid": process.pid, "started_at": time.time(),
            "last_progress_at": time.time(), "last_progress_signature": "0:0:false:false",
            "max_run_seconds": config.get("max_run_seconds") or 3600,
            "stale_timeout_seconds": config.get("stale_timeout_seconds") or 150,
            "cursors": {"twitter": 0, "reddit": 0},
            "max_rounds": int(config.get("rounds", config.get("max_rounds", 10))),
        }
        self._write_json(status_path, runtime)
        return runtime

    def apply_persona_overrides(self, simulation_id: str, personas: list[dict]) -> None:
        simulation_dir = self.data_dir / simulation_id
        by_agent = {}
        for persona in personas:
            raw_id = str(persona.get("id", ""))
            if raw_id.startswith("oasis-") and raw_id.removeprefix("oasis-").isdigit():
                by_agent[int(raw_id.removeprefix("oasis-"))] = persona
        if not by_agent:
            return
        reddit_path = simulation_dir / "reddit_profiles.json"
        reddit = self._read_json_list(reddit_path)
        for profile in reddit:
            persona = by_agent.get(int(profile.get("user_id", -1)))
            if persona:
                profile.update(name=persona.get("name", profile.get("name")),
                               persona=persona.get("profile", profile.get("persona")),
                               bio=persona.get("concern", profile.get("bio")))
        if reddit:
            self._write_json_value(reddit_path, reddit)
        twitter_path = simulation_dir / "twitter_profiles.csv"
        if twitter_path.exists():
            with twitter_path.open("r", encoding="utf-8", newline="") as source:
                rows = list(csv.DictReader(source))
                fields = source and (list(rows[0]) if rows else ["user_id", "name", "username", "user_char", "description"])
            for row in rows:
                persona = by_agent.get(int(row.get("user_id", -1)))
                if persona:
                    row["name"] = str(persona.get("name", row.get("name", "")))
                    row["user_char"] = str(persona.get("profile", row.get("user_char", "")))
                    row["description"] = str(persona.get("concern", row.get("description", "")))
            temporary = twitter_path.with_suffix(".csv.tmp")
            with temporary.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            temporary.replace(twitter_path)
        config_path = simulation_dir / "simulation_config.json"
        generated = self._read_json(config_path)
        for behavior in generated.get("agent_configs", []):
            persona = by_agent.get(int(behavior.get("agent_id", -1)))
            if persona:
                behavior["stance"] = persona.get("stance", behavior.get("stance"))
                behavior["influence_weight"] = persona.get("influence", behavior.get("influence_weight"))
        self._write_json(config_path, generated)

    def simulation_snapshot(self, simulation_id: str, cursor: str | None = None) -> dict:
        simulation_dir = self.data_dir / simulation_id
        status_path = simulation_dir / "direct_runtime.json"
        runtime = self._read_json(status_path)
        offsets = self._decode_cursor(cursor) if cursor else {"twitter": 0, "reddit": 0}
        actions: list[dict[str, Any]] = []
        completed: dict[str, bool] = {}
        rounds: dict[str, int] = {}
        next_offsets: dict[str, int] = {}
        log_sizes: dict[str, int] = {}
        for platform in ("twitter", "reddit"):
            log_path = simulation_dir / platform / "actions.jsonl"
            records, next_offset = self._read_log(log_path, offsets.get(platform, 0))
            next_offsets[platform] = next_offset
            log_sizes[platform] = self._file_size(log_path)
            completed[platform] = any(item.get("event_type") == "simulation_end" for item in self._read_all_log(log_path))
            platform_actions = [item for item in records if "agent_id" in item and "event_type" not in item]
            base_sequence = sum(
                1 for item in self._read_log_before(log_path, offsets.get(platform, 0))
                if "agent_id" in item and "event_type" not in item
            )
            for index, item in enumerate(platform_actions, base_sequence + 1):
                item.setdefault("platform", platform)
                item["source_sequence"] = int(item.get("source_sequence") or item.get("sequence") or index)
                item["source_id"] = item.get("source_id") or hashlib.sha256(
                    json.dumps(item, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
            actions.extend(platform_actions)
            rounds[platform] = max((int(item.get("round", 0)) for item in self._read_all_log(log_path)), default=0)
        pid_alive = self._pid_alive(runtime.get("pid"))
        progress_signature = ":".join(str(item) for item in (
            rounds.get("twitter", 0), rounds.get("reddit", 0),
            completed.get("twitter", False), completed.get("reddit", False),
            log_sizes.get("twitter", 0), log_sizes.get("reddit", 0),
            self._file_size(simulation_dir / "simulation.log"),
        ))
        if runtime.get("last_progress_signature") != progress_signature:
            runtime["last_progress_signature"] = progress_signature
            runtime["last_progress_at"] = time.time()
        max_seconds = runtime.get("max_run_seconds")
        stale_seconds = runtime.get("stale_timeout_seconds")
        if max_seconds and time.time() - float(runtime.get("started_at", time.time())) > float(max_seconds):
            self.stop_simulation(simulation_id)
            runtime["runner_status"] = "failed"
            runtime["error"] = "OASIS simulation exceeded its run timeout"
        elif all(completed.values()):
            runtime["runner_status"] = "completed"
        elif not pid_alive:
            runtime["runner_status"] = "failed"
            log_tail = self._read_text_tail(simulation_dir / "simulation.log")
            runtime["error"] = "OASIS process exited before both platforms completed"
            if log_tail:
                fatal_timeout = next(
                    (
                        line.split("Fatal timeout:", 1)[1].strip()
                        for line in reversed(log_tail.splitlines())
                        if "Fatal timeout:" in line
                    ),
                    None,
                )
                runtime["error"] += f"; {fatal_timeout or f'last output: {log_tail}'}"
        elif stale_seconds and time.time() - float(runtime.get("last_progress_at", time.time())) > float(stale_seconds):
            self.stop_simulation(simulation_id)
            runtime["runner_status"] = "failed"
            runtime["error"] = "OASIS simulation made no observable progress before its stale timeout"
        generated_config = self._read_json(simulation_dir / "simulation_config.json")
        natural_rounds = int(generated_config.get("time_config", {}).get("total_simulation_hours", 1) * 60 / max(1, generated_config.get("time_config", {}).get("minutes_per_round", 60)))
        total_rounds = max(1, int(runtime.get("max_rounds") or natural_rounds))
        current_round = max(rounds.values(), default=0)
        status = runtime | {
            "current_round": current_round,
            "total_rounds": total_rounds,
            "progress_percent": min(100, current_round / total_rounds * 100),
            "twitter_current_round": rounds.get("twitter", 0),
            "reddit_current_round": rounds.get("reddit", 0),
            "twitter_completed": completed.get("twitter", False),
            "reddit_completed": completed.get("reddit", False),
            "environment_alive": self.environment_alive(simulation_id),
        }
        self._write_json(status_path, runtime)
        return {"status": status, "actions": actions, "next_cursor": self._encode_cursor(next_offsets)}

    def stop_simulation(self, simulation_id: str) -> dict:
        simulation_dir = self.data_dir / simulation_id
        try:
            self._ipc(simulation_dir, "close_env", {}, timeout=10)
        except (TimeoutError, ProviderResponseError):
            runtime = self._read_json(simulation_dir / "direct_runtime.json")
            pid = runtime.get("pid")
            if self._pid_alive(pid):
                try:
                    os.killpg(int(pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 5
                while self._pid_alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.1)
                if self._pid_alive(pid):
                    try:
                        os.killpg(int(pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        return {"runner_status": "stopped"}

    def interview(self, simulation_id: str, interviews: list[dict], platform: str | None = None) -> dict:
        args: dict[str, Any] = {"interviews": interviews}
        if platform:
            args["platform"] = platform
        return self._ipc(self.data_dir / simulation_id, "batch_interview", args, timeout=120)

    def runtime_graph(self, graph_id: str) -> dict:
        return self._call("runtime-graph", {"graph_id": graph_id})

    def environment_alive(self, simulation_id: str) -> bool:
        return self._read_json(self.data_dir / simulation_id / "env_status.json").get("status") == "alive"

    def artifacts(self, simulation_id: str) -> dict:
        return self._call("artifacts", {"simulation_id": simulation_id})

    def generate_report(
        self, simulation_id: str, graph_id: str, simulation_requirement: str,
        language: str = "id", progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        report_timeout = float(os.getenv("OASIS_REPORT_TIMEOUT_SECONDS", "900"))
        payload = {
            "simulation_id": simulation_id, "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "language": language, "report_id": f"report_{uuid.uuid4().hex[:12]}",
        }
        if not progress_callback:
            return self._call("report", payload, timeout=max(self.timeout, report_timeout))

        process = subprocess.Popen(
            [str(self.runtime_python), str(self.bridge), "report"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=self._environment(),
        )
        completed: dict[str, str] = {}

        def communicate() -> None:
            stdout, stderr = process.communicate(json.dumps(payload, ensure_ascii=False))
            completed.update(stdout=stdout, stderr=stderr)

        thread = threading.Thread(target=communicate, daemon=True)
        thread.start()
        deadline = time.monotonic() + max(self.timeout, report_timeout)
        last_signature = ""
        while thread.is_alive():
            partial = self._report_progress(payload["report_id"])
            signature = json.dumps(partial, sort_keys=True, ensure_ascii=False) if partial else ""
            if partial and signature != last_signature:
                progress_callback(partial)
                last_signature = signature
            if time.monotonic() >= deadline:
                process.kill()
                thread.join(timeout=5)
                raise ProviderTransportError("report", f"timed out after {max(self.timeout, report_timeout):g}s")
            thread.join(timeout=0.5)
        if process.returncode:
            raise ProviderTransportError(
                "report", completed.get("stderr", "").strip() or completed.get("stdout", "").strip()
                or f"bridge exited {process.returncode}",
            )
        try:
            response = json.loads(completed.get("stdout", ""))
        except json.JSONDecodeError as error:
            raise ProviderResponseError("report", "invalid direct OASIS response") from error
        if not isinstance(response, dict) or not response.get("success"):
            raise ProviderResponseError("report", str(response.get("error", "direct OASIS operation failed")))
        return response.get("data") or {}

    def _report_progress(self, report_id: str) -> dict:
        folder = self.data_dir.parent / "reports" / report_id
        progress = self._read_json(folder / "progress.json")
        outline = self._read_json(folder / "outline.json")
        if not progress and not outline:
            return {}
        generated_sections = []
        outline_sections = outline.get("sections") if isinstance(outline.get("sections"), list) else []
        for path in sorted(folder.glob("section_*.md")):
            try:
                index = int(path.stem.split("_")[-1]) - 1
                markdown = path.read_text(encoding="utf-8").strip()
            except (OSError, ValueError):
                continue
            title = (outline_sections[index].get("title") if index < len(outline_sections) else None) or f"Bagian {index + 1}"
            heading = f"## {title}"
            content = markdown[len(heading):].strip() if markdown.startswith(heading) else markdown
            generated_sections.append({"index": index, "title": title, "content": content})
        return {
            "report_id": report_id, "outline": outline, "generated_sections": generated_sections,
            "status": progress.get("status", "planning"), "progress": progress.get("progress", 0),
            "message": progress.get("message"), "current_section": progress.get("current_section"),
            "updated_at": progress.get("updated_at"),
        }

    def ingest_actions(self, simulation_id: str, graph_id: str, run_id: str, actions: list[dict]) -> dict:
        ingestion_timeout = float(os.getenv("OASIS_INGESTION_TIMEOUT_SECONDS", "900"))
        return self._call(
            "ingest-actions",
            {
                "simulation_id": simulation_id, "graph_id": graph_id, "run_id": run_id,
                "actions": actions, "timeout_seconds": ingestion_timeout,
            },
            timeout=max(self.timeout, ingestion_timeout + 30),
        )

    def report_chat(self, simulation_id: str, graph_id: str, simulation_requirement: str,
                    message: str, history: list[dict] | None = None, language: str = "id") -> dict:
        return self._call("report-chat", {
            "simulation_id": simulation_id, "graph_id": graph_id,
            "simulation_requirement": simulation_requirement,
            "message": message, "history": history or [],
            "language": language,
        }, timeout=max(self.timeout, 300))

    def _ipc(self, simulation_dir: Path, command_type: str, args: dict, timeout: float) -> dict:
        import uuid
        command_id = str(uuid.uuid4())
        commands = simulation_dir / "ipc_commands"
        responses = simulation_dir / "ipc_responses"
        commands.mkdir(parents=True, exist_ok=True)
        responses.mkdir(parents=True, exist_ok=True)
        command = commands / f"{command_id}.json"
        self._write_json(command, {"command_id": command_id, "command_type": command_type, "args": args})
        response = responses / f"{command_id}.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if response.exists():
                value = self._read_json(response)
                command.unlink(missing_ok=True)
                response.unlink(missing_ok=True)
                if value.get("status") != "completed":
                    raise ProviderResponseError("interview", str(value.get("error", "IPC command failed")))
                return value.get("result") or {}
            time.sleep(0.25)
        command.unlink(missing_ok=True)
        raise TimeoutError(f"OASIS {command_type} timed out")

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _read_json_list(path: Path) -> list[dict]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _write_json_value(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _pid_alive(pid: Any) -> bool:
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
            stat_path = Path(f"/proc/{int(pid)}/stat")
            if stat_path.exists():
                fields = stat_path.read_text(encoding="utf-8").split()
                if len(fields) > 2 and fields[2] == "Z":
                    return False
            return True
        except (OSError, ValueError):
            return False

    @staticmethod
    def _encode_cursor(offsets: dict[str, int]) -> str:
        return f"{offsets.get('twitter', 0)}:{offsets.get('reddit', 0)}"

    @staticmethod
    def _decode_cursor(cursor: str) -> dict[str, int]:
        try:
            twitter, reddit = cursor.split(":", 1)
            return {"twitter": int(twitter), "reddit": int(reddit)}
        except (ValueError, AttributeError):
            return {"twitter": 0, "reddit": 0}

    @staticmethod
    def _read_log(path: Path, offset: int) -> tuple[list[dict], int]:
        if not path.exists():
            return [], offset
        records = []
        with path.open("r", encoding="utf-8") as source:
            source.seek(offset)
            for line in source:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return records, source.tell()

    @classmethod
    def _read_all_log(cls, path: Path) -> list[dict]:
        return cls._read_log(path, 0)[0]

    @staticmethod
    def _read_log_before(path: Path, offset: int) -> list[dict]:
        if not path.exists() or offset <= 0:
            return []
        records = []
        with path.open("r", encoding="utf-8") as source:
            content = source.read(offset)
        for line in content.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    @staticmethod
    def _file_size(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    @staticmethod
    def _read_text_tail(path: Path, limit: int = 2000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
        except OSError:
            return ""
