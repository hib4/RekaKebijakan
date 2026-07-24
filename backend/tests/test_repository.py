from app.repository import Repository


def test_repository_persists_state_and_recovers_jobs(tmp_path):
    path = tmp_path / "state.sqlite3"
    repository = Repository(str(path))
    state = {"id": "sim-1", "project": {"id": "project-1"}, "updated_at": "now", "value": 1}
    repository.create(state)
    repository.mutate("sim-1", lambda item: item.update(value=2))
    assert repository.put_job("job-1", "sim-1", "graph", "running", {"rounds": 3})

    reopened = Repository(str(path))
    assert reopened.get("sim-1")["value"] == 2
    jobs = reopened.recoverable_jobs()
    assert jobs[0]["stage"] == "graph"
    assert jobs[0]["config"] == {"rounds": 3}
    assert reopened.job_status("job-1") == "queued"
    reopened.set_job_status("job-1", "paused")
    assert not reopened.claim_job("job-1")
    assert reopened.job_status("job-1") == "paused"


def test_repository_allows_only_one_active_job_per_simulation(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    first = Repository(str(path))
    second = Repository(str(path))
    assert first.put_job("job-1", "sim-1", "graph", "queued", {})
    assert not second.put_job("job-2", "sim-1", "environment", "queued", {})
    first.set_job_status("job-1", "completed")
    assert second.put_job("job-2", "sim-1", "environment", "queued", {})
