"""Exercise the production binary outside the checkout without a Python bridge."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="stake-engine-é-") as temporary:
        data = Path(temporary)
        shutil.copyfile(root / "config.yaml", data / "config.yaml")
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("PYTHON", "STAKE_", "VIRTUAL_ENV", "CONDA_"))
        }
        env["STAKE_DATA_DIR"] = str(data)
        env["PYTHONPATH"] = str(data / "nonexistent")
        env["STAKE_PYTHON"] = str(data / "nonexistent")

        def request(command: str, payload: dict | None = None) -> dict:
            result = json.loads(
                subprocess.check_output(
                    [str(executable), command, json.dumps(payload or {})],
                    cwd=data,
                    env=env,
                    timeout=30,
                )
            )

            if not isinstance(result, dict):
                raise ValueError("Backend returned a non-object response")
            return result

        health = request("health")
        assert health["frozen"] and health["protocol"] == 1
        assert health["python"] == "3.13.16", health
        assert "curl" in health["native_tls"].lower()
        config = request("get-config")
        assert config["success"] and len(config["config"]["mirrors"]) > 0
        assert request("update-config", {"timeout_seconds": 17})["success"]
        assert request("get-config")["config"]["settings"]["timeout_seconds"] == 17
        assert request("get-history-stats")["success"]
        print(
            "PASS production frozen backend: health/native TLS/config/settings/SQLite outside checkout",
            health["architecture"],
        )


if __name__ == "__main__":
    main()
