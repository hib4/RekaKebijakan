from app.repository import Repository


def test_repository_persists_state_and_recovers_jobs(tmp_path):
    path = tmp_path / "state.sqlite3"
    repository = Repository(str(path))
    state = {"id": "sim-1", "project": {"id": "project-1"}, "updated_at": "now", "value": 1}
    repository.create(state)
    repository.mutate("sim-1", lambda item: item.update(value=2))
    repository.put_job("job-1", "sim-1", "graph", "running", {"rounds": 3})

    reopened = Repository(str(path))
    assert reopened.get("sim-1")["value"] == 2
    jobs = reopened.recoverable_jobs()
    assert jobs[0]["stage"] == "graph"
    assert jobs[0]["config"] == {"rounds": 3}
    assert reopened.job_status("job-1") == "queued"
    reopened.set_job_status("job-1", "paused")
    reopened.claim_job("job-1")
    assert reopened.job_status("job-1") == "paused"
