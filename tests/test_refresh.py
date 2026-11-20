"""Tests for the refresh job endpoints. The refresher container is mocked
(no R runs) and so is the loader (the test database is not reloaded)."""

import pytest

from app.db import db
from app.services import refresh


class FakeRefresher:
    """Stands in for refresher/server.py."""

    def __init__(self, up=True):
        self.up = up
        self.jobs = {}
        self.start_status = 202

    def health(self):
        return self.up

    def start(self, job_id):
        if self.start_status != 202:
            return self.start_status, {"error": "A refresh is already running."}
        self.jobs[job_id] = {"state": "running", "step": "Pulling games..."}
        return 202, {"job_id": job_id}

    def job(self, job_id):
        if not self.up:
            return None, None
        return (200, dict(self.jobs[job_id])) if job_id in self.jobs else (404, {"error": "No such job."})


@pytest.fixture
def fake(client_app, monkeypatch):
    f = FakeRefresher()
    monkeypatch.setattr(refresh, "refresher_up", f.health)
    monkeypatch.setattr(refresh, "refresher_start", f.start)
    monkeypatch.setattr(refresh, "refresher_job", f.job)
    monkeypatch.setattr(refresh, "RELOAD_IN_THREAD", False)
    db.refresh_jobs.delete_many({})
    yield f
    db.refresh_jobs.delete_many({})


@pytest.fixture
def fake_loader(monkeypatch):
    """The loader adds 3 games and moves the data date forward."""
    calls = []

    def main():
        calls.append(1)
        db.schedule.insert_many([{"_id": f"new{i}"} for i in range(3)])
        db.meta.update_one({"_id": "seed"}, {"$set": {"data_as_of": "2026-11-19", "pulled_at": "2026-11-20T18:00:00Z"}},
                           upsert=True)

    monkeypatch.setattr(refresh.loader, "main", main)
    yield calls
    db.schedule.delete_many({"_id": {"$regex": "^new"}})


def test_refresher_down(client_app, fake):
    fake.up = False
    status = client_app.get("/api/refresh/status").get_json()
    assert status["refresher"] is False and "--profile refresh" in status["how_to_start"]
    res = client_app.post("/api/refresh")
    assert res.status_code == 503 and "docker compose --profile refresh up" in res.get_json()["error"]
    assert db.refresh_jobs.count_documents({}) == 0


def test_start_poll_reload_done(client_app, fake, fake_loader):
    res = client_app.post("/api/refresh")
    assert res.status_code == 202
    job_id = res.get_json()["job_id"]
    assert client_app.get("/api/refresh/status").get_json()["job"]["job_id"] == job_id

    fake.jobs[job_id]["step"] = "Pulling shots..."
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "pulling" and job["step"] == "Pulling shots..."
    assert fake_loader == []  # no reload while the pulls run

    fake.jobs[job_id] = {"state": "done", "step": "Pulls finished"}
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "done" and fake_loader == [1]
    assert {"collection": "schedule", "change": 3} == {k: v for k, v in job["changes"][0].items() if k in ("collection", "change")}
    assert job["freshness"]["data_as_of"] == "2026-11-19"
    # Polling again does not reload twice, and the job is no longer active.
    client_app.get(f"/api/refresh/{job_id}")
    assert fake_loader == [1]
    assert client_app.get("/api/refresh/status").get_json()["job"] is None


def test_only_one_job_at_a_time(client_app, fake):
    first = client_app.post("/api/refresh").get_json()["job_id"]
    res = client_app.post("/api/refresh")
    assert res.status_code == 409
    assert res.get_json()["job_id"] == first
    assert db.refresh_jobs.count_documents({"active": True}) == 1


def test_the_index_rejects_a_second_active_job(client_app, fake):
    from pymongo.errors import DuplicateKeyError
    db.refresh_jobs.insert_one({"active": True, "state": "pulling"})
    with pytest.raises(DuplicateKeyError):
        db.refresh_jobs.insert_one({"active": True, "state": "pulling"})
    db.refresh_jobs.insert_one({"state": "done"})  # finished jobs are not limited


def test_failed_pull_reports_the_step_and_error(client_app, fake, fake_loader):
    job_id = client_app.post("/api/refresh").get_json()["job_id"]
    fake.jobs[job_id] = {"state": "failed", "step": "Pulling shots...", "error": "Error: could not resolve host",
                         "log_tail": ["Error: could not resolve host"]}
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "failed"
    assert job["error"].startswith("Pulling shots failed: Error: could not resolve host")
    assert fake_loader == []
    # A new refresh can start after a failure.
    assert client_app.post("/api/refresh").status_code == 202


def test_refresher_restart_fails_the_job(client_app, fake):
    job_id = client_app.post("/api/refresh").get_json()["job_id"]
    fake.jobs.clear()
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "failed" and "restarted" in job["error"]


def test_refresher_not_answering_keeps_the_job(client_app, fake):
    job_id = client_app.post("/api/refresh").get_json()["job_id"]
    fake.up = False
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "pulling" and "Waiting" in job["step_note"]


def test_reload_error_is_reported(client_app, fake, monkeypatch):
    def broken():
        raise RuntimeError("disk full")
    monkeypatch.setattr(refresh.loader, "main", broken)
    job_id = client_app.post("/api/refresh").get_json()["job_id"]
    fake.jobs[job_id] = {"state": "done"}
    job = client_app.get(f"/api/refresh/{job_id}").get_json()
    assert job["state"] == "failed" and "disk full" in job["error"]


def test_refresher_rejects_the_start(client_app, fake):
    fake.start_status = 409
    res = client_app.post("/api/refresh")
    assert res.status_code == 409
    assert db.refresh_jobs.count_documents({"active": True}) == 0


def test_bad_and_unknown_job_ids(client_app, fake):
    assert client_app.get("/api/refresh/nope").status_code == 400
    assert client_app.get("/api/refresh/64b000000000000000000000").status_code == 404
