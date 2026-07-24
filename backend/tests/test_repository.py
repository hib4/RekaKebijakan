from datetime import datetime, timezone

from app.repository import Repository


def test_repository_persists_state_and_recovers_jobs(database_url):
    repository = Repository(database_url)
    state = {"id": "sim-1", "project": {"id": "project-1"}, "updated_at": datetime.now(timezone.utc).isoformat(), "value": 1}
    repository.create(state)
    repository.mutate("sim-1", lambda item: item.update(value=2))
    assert repository.put_job("job-1", "sim-1", "graph", "running", {"rounds": 3})

    reopened = Repository(database_url)
    assert reopened.get("sim-1")["value"] == 2
    jobs = reopened.recoverable_jobs()
    assert jobs[0]["stage"] == "graph"
    assert jobs[0]["config"] == {"rounds": 3}
    assert reopened.job_status("job-1") == "queued"
    reopened.set_job_status("job-1", "paused")
    assert not reopened.claim_job("job-1")
    assert reopened.job_status("job-1") == "paused"


def test_repository_allows_only_one_active_job_per_simulation(database_url):
    first = Repository(database_url)
    second = Repository(database_url)
    first.create({"id": "sim-1", "project": {"id": "project-1"}, "updated_at": datetime.now(timezone.utc).isoformat()})
    assert first.put_job("job-1", "sim-1", "graph", "queued", {})
    assert not second.put_job("job-2", "sim-1", "environment", "queued", {})
    first.set_job_status("job-1", "completed")
    assert second.put_job("job-2", "sim-1", "environment", "queued", {})
