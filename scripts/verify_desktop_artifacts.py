"""Validate the explicit release file inventory and hash final installer bytes."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = json.loads((root / "gui/package.json").read_text())["version"]
    prefix = f"Stake-Mirrors-Ping-{version}"
    expected = {
        f"{prefix}-mac-{arch}.{ext}"
        for arch in ("x64", "arm64")
        for ext in ("dmg", "zip")
    }
    expected |= {f"{prefix}-win-x64-{target}.exe" for target in ("setup", "portable")}
    # electron-builder expands ${arch} to the native package architecture label.
    expected |= {
        f"{prefix}-linux-amd64.deb",
        f"{prefix}-linux-x86_64.AppImage",
        f"{prefix}-linux-x86_64.rpm",
    }
    actual = {
        p.name: p
        for p in args.directory.rglob("*")
        if p.is_file()
        and p.suffix in (".dmg", ".zip", ".exe", ".AppImage", ".deb", ".rpm")
    }
    installers = [
        p
        for p in args.directory.rglob("*")
        if p.is_file()
        and p.suffix in (".dmg", ".zip", ".exe", ".AppImage", ".deb", ".rpm")
    ]
    if len(installers) != len(actual) or any(
        p.parent != args.directory for p in installers
    ):
        raise SystemExit("Nested or duplicate candidate filenames")
    if set(actual) != expected:
        raise SystemExit(
            f"Unexpected release inventory. Missing: {expected - set(actual)}; extra: {set(actual) - expected}"
        )
    lines = []
    manifest = []
    for name in sorted(expected):
        file = actual[name]
        if file.stat().st_size < 1024 * 1024:
            raise SystemExit(f"Installer is unexpectedly small: {name}")
        with file.open("rb") as stream:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
            digest = hasher.hexdigest()
        lines.append(f"{digest}  {name}")
        manifest.append({"name": name, "size": file.stat().st_size, "sha256": digest})
    (args.directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    (args.directory / "release-manifest.json").write_text(
        json.dumps(
            {
                "version": version,
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
                "signed": False,
                "notarized": False,
                "files": manifest,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"Verified {len(expected)} candidate files; checksums generated from final bytes. Not published."
    )


if __name__ == "__main__":
    main()
