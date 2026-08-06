import ast
import importlib.util
import json
from pathlib import Path


LOCAL_SCRIPTS = Path(__file__).resolve().parents[1] / "oasis_engine_runtime" / "scripts"
SCRIPTS = LOCAL_SCRIPTS if LOCAL_SCRIPTS.exists() else Path(
    "/opt/rekakebijakan/oasis_engine_runtime/scripts"
)


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_selects_an_agent_before_configured_active_hours():
    schedule = load_script("activity_schedule")

    class RejectingRandom:
        @staticmethod
        def uniform(_minimum, _maximum):
            return 1

        @staticmethod
        def random():
            return 1

        @staticmethod
        def sample(values, count):
            return values[:count]

    selected = schedule.select_active_agent_ids({
        "time_config": {
            "agents_per_hour_min": 1,
            "agents_per_hour_max": 5,
            "off_peak_hours": [0],
            "off_peak_activity_multiplier": 0.05,
        },
        "agent_configs": [
            {"agent_id": 1, "active_hours": [9], "activity_level": 0.7},
            {"agent_id": 2, "active_hours": [9], "activity_level": 0.7},
        ],
    }, current_hour=0, rng=RejectingRandom())

    assert selected == [1]


def test_round_logger_marks_missing_trace_as_synthetic_failure(tmp_path):
    action_logger = load_script("action_logger")
    logger = action_logger.PlatformActionLogger("twitter", str(tmp_path))

    count = logger.log_round_actions(
        1,
        active_agent_ids=[1, 2],
        actions=[{
            "agent_id": 1,
            "agent_name": "Rina",
            "action_type": "CREATE_POST",
            "action_args": {"content": "Pendapat warga"},
        }],
        agent_names={1: "Rina", 2: "Budi"},
    )
    records = [
        json.loads(line)
        for line in (tmp_path / "twitter" / "actions.jsonl").read_text().splitlines()
    ]

    assert count == 1
    assert [record["action_type"] for record in records] == ["CREATE_POST", "DO_NOTHING"]
    assert records[1]["agent_id"] == 2
    assert records[1]["success"] is False
    assert records[1]["synthetic"] is True


def test_parallel_oasis_model_uses_waf_safe_request_headers():
    tree = ast.parse((SCRIPTS / "run_parallel_simulation.py").read_text())
    create_model = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_model"
    )
    factory_call = next(
        node for node in ast.walk(create_model)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ModelFactory"
        and node.func.attr == "create"
    )
    headers = next(
        keyword.value for keyword in factory_call.keywords
        if keyword.arg == "default_headers"
    )

    assert isinstance(headers, ast.Call)
    assert isinstance(headers.func, ast.Name) and headers.func.id == "dict"
    assert isinstance(headers.args[0], ast.Name)
    assert headers.args[0].id == "DEFAULT_REQUEST_HEADERS"
    keywords = {keyword.arg: keyword.value for keyword in factory_call.keywords}
    assert isinstance(keywords["timeout"], ast.Name)
    assert keywords["timeout"].id == "request_timeout"
    assert isinstance(keywords["max_retries"], ast.Constant)
    assert keywords["max_retries"].value == 0


def test_disable_model_retries_updates_camel_and_openai_clients():
    compat = load_script("../app/utils/openai_chat_compat")

    class Client:
        max_retries = 3

    class Model:
        _max_retries = 3
        _client = Client()
        _async_client = Client()

    model = Model()

    assert compat.disable_model_retries(model) is model
    assert model._max_retries == 0
    assert model._client.max_retries == 0
    assert model._async_client.max_retries == 0


def test_agent_output_language_preserves_tool_configuration():
    agent_language = load_script("agent_language")
    tools = {"create_post": object(), "create_comment": object()}

    class Agent:
        output_language = None
        tool_dict = tools

    agents = [Agent(), Agent()]

    class Graph:
        @staticmethod
        def get_agents():
            return enumerate(agents)

    agent_language.apply_output_language(Graph(), "id")

    assert [agent.output_language for agent in agents] == ["Bahasa Indonesia"] * 2
    assert all(agent.tool_dict is tools for agent in agents)


def test_parallel_oasis_applies_language_to_both_agent_graphs():
    tree = ast.parse((SCRIPTS / "run_parallel_simulation.py").read_text())
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "apply_output_language"
    ]

    assert len(calls) == 2
    assert all(isinstance(call.args[0], ast.Attribute) for call in calls)


def test_parallel_oasis_uses_bounded_platform_concurrency():
    tree = ast.parse((SCRIPTS / "run_parallel_simulation.py").read_text())
    semaphore_values = [
        keyword.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "oasis"
        and node.func.attr == "make"
        for keyword in node.keywords
        if keyword.arg == "semaphore"
    ]

    assert len(semaphore_values) == 2
    assert all(isinstance(value, ast.Call) for value in semaphore_values)
