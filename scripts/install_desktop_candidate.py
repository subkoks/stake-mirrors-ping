"""Install/extract into a disposable Unicode path; never touch host applications."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args()
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    dist = ROOT / "gui" / ("dist-fixture" if args.fixture else "dist")
    parent = Path(
        tempfile.mkdtemp(prefix="stake-installed-é-", dir=os.environ.get("RUNNER_TEMP"))
    )
    destination = parent / "Desktop application Å"
    destination.mkdir()
    if sys.platform == "darwin":
        source = (
            dist
            / ("mac-arm64" if arch == "arm64" else "mac")
            / "Stake Mirrors Ping.app"
        )
        if args.fixture:
            shutil.copytree(source, destination / source.name, symlinks=True)
        else:
            image = next(dist.glob("*.dmg"))
            mount = parent / "mounted"
            mount.mkdir()
            subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    "-readonly",
                    "-nobrowse",
                    "-mountpoint",
                    str(mount),
                    str(image),
                ],
                check=True,
            )
            try:
                subprocess.run(
                    ["ditto", str(mount / source.name), str(destination / source.name)],
                    check=True,
                )
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        executable = destination / source.name / "Contents/MacOS/Stake Mirrors Ping"
    elif sys.platform == "win32":
        if args.fixture:
            shutil.copytree(dist / "win-unpacked", destination, dirs_exist_ok=True)
        else:
            installer = next(dist.glob("*-setup.exe"))
            subprocess.run(
                [str(installer), "/S", "/D=" + str(destination)],
                check=True,
                timeout=180,
            )
        executable = destination / "Stake Mirrors Ping.exe"
        if not args.fixture and os.environ.get("GITHUB_ENV"):
            with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as env:
                env.write(f"STAKE_DESKTOP_INSTALLER={installer}\n")
    else:
        if args.fixture:
            shutil.copytree(
                dist / "linux-unpacked", destination, dirs_exist_ok=True, symlinks=True
            )
        else:
            package = next(dist.glob("*.deb"))
            subprocess.run(
                ["dpkg-deb", "-x", str(package), str(destination)], check=True
            )
            destination = destination / "opt/Stake Mirrors Ping"
        executable = destination / "stake-mirrors-ping-gui"
    if not executable.is_file():
        raise SystemExit(f"Installed executable was not found: {executable}")
    if os.environ.get("GITHUB_ENV"):
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as env:
            env.write(
                f"STAKE_DESKTOP_EXECUTABLE={executable}\nSTAKE_E2E_OUTPUT={os.environ['RUNNER_TEMP']}\n"
            )
    print(f"INSTALLED_EXECUTABLE={executable}")


if __name__ == "__main__":
    main()
