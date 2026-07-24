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


def test_worker_lease_allows_only_one_claim(database_url):
    repository = Repository(database_url)
    repository.create({"id": "sim-lease", "project": {"id": "project-lease"}, "updated_at": datetime.now(timezone.utc).isoformat()})
    assert repository.put_job("job-lease", "sim-lease", "graph", "queued", {})
    claimed = repository.claim_next_job("worker-a", lease_seconds=60)
    assert claimed and claimed["id"] == "job-lease"
    assert repository.claim_next_job("worker-b", lease_seconds=60) is None
    assert not repository.finish_job("job-lease", "worker-b", claimed["execution_token"])
    assert repository.renew_job_lease("job-lease", "worker-a", claimed["execution_token"], 60)
    assert not repository.finish_job("job-lease", "worker-a", "stale-token")
    assert repository.finish_job("job-lease", "worker-a", claimed["execution_token"])


def test_full_text_chunk_search_is_scoped(database_url):
    repository = Repository(database_url)
    repository.create({"id": "sim-search", "project": {"id": "project-search"}, "updated_at": datetime.now(timezone.utc).isoformat()})
    document = {"id": "doc-search", "simulation_id": "sim-search", "name": "policy.txt", "path": "/tmp/policy.txt", "text": "akses pelabuhan untuk nelayan"}
    repository.add_document_with_chunks(document, [{
        "id": "chunk-search", "document_id": "doc-search", "ordinal": 0, "text": document["text"],
        "char_start": 0, "char_end": len(document["text"]), "content_sha256": "a" * 64, "metadata": {},
    }])
    matches = repository.search_chunks("sim-search", "pelabuhan nelayan")
    assert [item["id"] for item in matches] == ["chunk-search"]
    assert repository.search_chunks("sim-search", "rumah sakit") == []
