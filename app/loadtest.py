import logging
import subprocess
import sys
import time

_logger = logging.getLogger(__name__)


def run_loadtest(
    run_id: str,
    host: str,
    users: int,
    spawn_rate: int,
    run_time: str,
) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "load/locustfile.py",
        "--headless",
        "-u",
        str(users),
        "-r",
        str(spawn_rate),
        "-t",
        run_time,
        "--host",
        host,
        "--only-summary",
    ]

    start = time.perf_counter()
    try:
        _logger.info(
            "Loadtest start run_id=%s users=%s spawn_rate=%s run_time=%s host=%s",
            run_id,
            users,
            spawn_rate,
            run_time,
            host,
        )
        proc = subprocess.run(cmd, capture_output=True, text=True)
        duration_ms = (time.perf_counter() - start) * 1000
        _logger.info("Loadtest done run_id=%s exit_code=%s duration_ms=%.2f", run_id, proc.returncode, duration_ms)
        return {
            "status": "finished" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "stdout": proc.stdout[-50_000:],  # keep bounded
            "stderr": proc.stderr[-50_000:],
        }
    except Exception as e:
        _logger.exception("Loadtest job failed: %s", e)
        return {"status": "failed", "error": str(e)}

