"""Build a native, private desktop runtime from the locked environment."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    arch = {"AMD64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}[
        platform.machine()
    ]
    target = f"{sys.platform}-{arch}"
    output = (
        ROOT
        / "packaging/output"
        / ("fixture" if args.fixture else "production")
        / target
    )
    entry = ROOT / (
        "gui/e2e/frozen_fixture.py" if args.fixture else "packaging/backend_entry.py"
    )
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stake-freeze-") as temporary:
        spec = Path(temporary) / "backend.spec"
        spec.write_text(
            f"ROOT={str(ROOT)!r}\nENTRY={str(entry)!r}\n"
            + (ROOT / "packaging/backend.spec").read_text()
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                "--distpath",
                str(output),
                "--workpath",
                str(Path(temporary) / "work"),
                str(spec),
            ],
            check=True,
            cwd=ROOT,
        )
    backend = output / "stake-backend"
    executable = backend / (
        "stake-backend.exe" if sys.platform == "win32" else "stake-backend"
    )
    response = json.loads(
        subprocess.check_output(
            [str(executable), "health"],
            cwd=temporary if Path(temporary).exists() else output,
            timeout=30,
        )
    )
    assert response["frozen"] and response["architecture"] == arch, response
    notices = backend / "licenses"
    notices.mkdir(exist_ok=True)
    packages = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        packages.append(
            {
                "name": name,
                "version": dist.version,
                "license": dist.metadata.get("License-Expression")
                or dist.metadata.get("License")
                or "See bundled license files",
            }
        )
        for item in dist.files or []:
            if any(
                word in item.name.lower() for word in ("license", "copying", "notice")
            ):
                source = Path(str(dist.locate_file(item)))
                if source.is_file():
                    destination = notices / name / str(item).replace("..", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
    with urllib.request.urlopen(
        f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE",
        timeout=30,
    ) as response_file:
        (notices / "PYTHON-LICENSE.txt").write_bytes(response_file.read())
    files = {
        str(p.relative_to(backend)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(backend.rglob("*"))
        if p.is_file()
    }
    provenance = {
        "schema": 1,
        "version": importlib.metadata.version("stake-mirrors-ping"),
        "target": target,
        "python": platform.python_version(),
        "fixture": args.fixture,
        "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "build_environment": sorted(packages, key=lambda p: p["name"]),
        "files": files,
    }
    (backend / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"BACKEND_READY {backend}")


if __name__ == "__main__":
    main()
