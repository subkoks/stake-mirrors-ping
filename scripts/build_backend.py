"""Build a native, private desktop runtime from the locked environment."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
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
    if platform.python_version() != "3.13.16":
        raise SystemExit(
            "Build with uv run --python 3.13.16 --locked --group desktop python scripts/build_backend.py"
        )
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
    shutil.copytree(
        ROOT / "packaging/vendor-licenses", notices / "native", dirs_exist_ok=True
    )
    shutil.copyfile(
        ROOT / "packaging/vendor-license-sources.txt", notices / "native-sources.txt"
    )
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
    requirements = set()
    for binary in backend.rglob("*"):
        if not binary.is_file() or binary.is_symlink():
            continue
        with binary.open("rb") as stream:
            magic = stream.read(4)
        if sys.platform == "linux" and magic == b"\x7fELF":
            info = subprocess.check_output(
                ["readelf", "--version-info", str(binary)], text=True
            )
            for value in re.findall(r"GLIBC_(\d+\.\d+)", info):
                requirements.add(value)
                if tuple(map(int, value.split("."))) > (2, 35):
                    raise SystemExit(
                        f"Backend exceeds Ubuntu 22.04 glibc baseline: {binary.name} GLIBC_{value}"
                    )
        elif sys.platform == "darwin" and magic in (
            b"\xcf\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
        ):
            info = subprocess.check_output(["otool", "-l", str(binary)], text=True)
            minimum_blocks = [
                block
                for block in re.split(r"Load command \d+", info)
                if "cmd LC_BUILD_VERSION" in block
                or "cmd LC_VERSION_MIN_MACOSX" in block
            ]
            for value in re.findall(
                r"(?:minos|\bversion) (\d+\.\d+(?:\.\d+)?)", "\n".join(minimum_blocks)
            ):
                requirements.add(value)
                if tuple(map(int, value.split(".")[:2])) > (13, 0):
                    raise SystemExit(
                        f"Backend exceeds macOS 13 deployment baseline: {binary.name} {value}"
                    )
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
        "python_distribution": "actions/python-versions via pinned setup-python"
        if os.environ.get("GITHUB_ACTIONS")
        else "local Python build (see interpreter version and embedded binary hashes)",
        "native_abi_versions": sorted(requirements),
        "fixture": args.fixture,
        "lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "build_environment": sorted(packages, key=lambda p: p["name"]),
        "files": files,
    }
    (backend / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"BACKEND_READY {backend}")


if __name__ == "__main__":
    main()
