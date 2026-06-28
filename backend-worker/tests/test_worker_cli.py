import subprocess
import sys
from pathlib import Path


def test_worker_once_exits_successfully():
    worker_path = Path(__file__).resolve().parents[1] / "worker.py"

    result = subprocess.run(
        [sys.executable, str(worker_path), "--once"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "backend-worker ready" in result.stdout
