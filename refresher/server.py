"""A tiny job server for the refresher container (Python standard library only).

It runs the R pull scripts in the same order as refresh.sh, one job at a
time, and reports progress. It is reachable only on the internal Docker
network (docker-compose.yml gives it no ports).

    GET  /health             {"ok": true}
    POST /jobs  {"job_id"}   start the pulls, 202; 409 if a job is running
    GET  /jobs/<job_id>      {"state", "step", "script", "error", "log_tail"}

state is "running", "done" or "failed". The web app reloads MongoDB itself
after "done".
"""

import json
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Same scripts and order as refresh.sh. Keep the two lists in sync.
SCRIPTS = [
    ("pulls/pull_core.R", "Pulling games..."),
    ("pulls/pull_shots.R", "Pulling shots..."),
    ("pulls/pull_stats.R", "Pulling player stats..."),
]
SCRIPT_TIMEOUT = 20 * 60  # seconds per script
WORKDIR = "/work"         # holds pulls/ and data/seed/

jobs = {}
lock = threading.Lock()


def run_job(job_id):
    job = jobs[job_id]
    for script, step in SCRIPTS:
        with lock:
            job.update(step=step, script=script)
        tail = deque(maxlen=40)
        try:
            proc = subprocess.Popen(["Rscript", script], cwd=WORKDIR, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace")
            # A watchdog, not a check between lines: a stalled download prints
            # nothing, so the script is killed after SCRIPT_TIMEOUT either way.
            timed_out = threading.Event()

            def stop():
                timed_out.set()
                proc.kill()

            watchdog = threading.Timer(SCRIPT_TIMEOUT, stop)
            watchdog.start()
            for line in proc.stdout:
                tail.append(line.rstrip())
                print(f"[{script}] {line.rstrip()}", flush=True)
            code = proc.wait()
            watchdog.cancel()
            if timed_out.is_set():
                tail.append(f"Stopped after {SCRIPT_TIMEOUT // 60} minutes with no finish. "
                            "A download may have stalled")
        except OSError as err:
            code = 1
            tail.append(str(err))
        with lock:
            job["log_tail"] = list(tail)[-12:]
        if code != 0:
            errors = [l for l in tail if l.startswith("Error") or "error" in l.lower()]
            with lock:
                job.update(state="failed", error=(errors[-1] if errors else (tail[-1] if tail else "no output")),
                           finished_at=time.time())
            return
    with lock:
        job.update(state="done", step="Pulls finished", finished_at=time.time())


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self.send(200, {"ok": True})
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/", 2)[2]
            with lock:
                job = dict(jobs[job_id]) if job_id in jobs else None
            return self.send(200, job) if job else self.send(404, {"error": "No such job."})
        return self.send(404, {"error": "Not found."})

    def do_POST(self):
        if self.path != "/jobs":
            return self.send(404, {"error": "Not found."})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            job_id = str(body["job_id"])
        except (ValueError, KeyError):
            return self.send(400, {"error": "Send {\"job_id\": ...}."})
        with lock:
            if any(j["state"] == "running" for j in jobs.values()):
                return self.send(409, {"error": "A refresh is already running."})
            jobs[job_id] = {"job_id": job_id, "state": "running", "step": "Starting...", "script": None,
                            "error": None, "log_tail": [], "started_at": time.time()}
        threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
        return self.send(202, {"job_id": job_id})

    def log_message(self, fmt, *args):  # keep the container log to the R output
        pass


if __name__ == "__main__":
    print("Refresher listening on port 8080 (internal network only).", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
