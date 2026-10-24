"""Prepare only a draft from an existing approved tag and successful exact-source CI.

Never creates/moves a tag or publishes a release. Run only after final candidate
approval. GitHub authentication is supplied by the workflow, never printed.
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

REPO = "subkoks/stake-mirrors-ping"


def output(*args: str) -> str:
    return subprocess.check_output(list(args), text=True).strip()


def main() -> None:
    tag, run_id = os.environ["RELEASE_TAG"], os.environ["BUILD_RUN_ID"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or not re.fullmatch(r"\d+", run_id):
        raise SystemExit("Invalid approved tag or run identifier")
    commit = output("git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"], check=True
    )
    run = json.loads(output("gh", "api", f"repos/{REPO}/actions/runs/{run_id}"))
    if (
        run["head_sha"] != commit
        or run["conclusion"] != "success"
        or run["head_repository"]["full_name"] != REPO
        or run["path"] != ".github/workflows/build.yml"
        or run["event"] not in ("push", "workflow_dispatch")
    ):
        raise SystemExit("Candidate run does not validate the approved tag commit")
    with tempfile.TemporaryDirectory(prefix="stake-approved-release-") as temporary:
        directory = Path(temporary)
        subprocess.run(
            [
                "gh",
                "run",
                "download",
                run_id,
                "-R",
                REPO,
                "--name",
                "desktop-release-candidate",
                "--dir",
                str(directory),
            ],
            check=True,
        )
        manifest = json.loads((directory / "release-manifest.json").read_text())
        if (
            "v" + manifest["version"] != tag
            or manifest["source_commit"] != commit
            or len(manifest["files"]) != 9
        ):
            raise SystemExit("Candidate manifest/source mismatch")
        expected = {item["name"] for item in manifest["files"]} | {
            "SHA256SUMS.txt",
            "release-manifest.json",
        }
        if {file.name for file in directory.iterdir()} != expected:
            raise SystemExit("Unexpected candidate files")
        for item in manifest["files"]:
            name = item["name"]
            if Path(name).name != name:
                raise SystemExit("Unsafe candidate filename")
            file = directory / name
            with file.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != item["sha256"] or file.stat().st_size != item["size"]:
                raise SystemExit("Candidate checksum/size mismatch")
        notes = directory / "notes.md"
        notes.write_text(
            f"Self-contained desktop candidate {tag}. Includes its Python scan engine; no Python/Node installation is needed.\n\nWindows x64, macOS Intel/Apple Silicon (13+), Linux x64 (Ubuntu baseline).\n\nSigning: unsigned; macOS not notarized. See the desktop distribution guide and final candidate review for validation limits. No automatic update installation.\n\nValidated source: {commit}\nBuild: https://github.com/{REPO}/actions/runs/{run_id}\n\nDo not publish until the final asset list, signing status, and approval have been checked.\n"
        )
        files = [str(directory / name) for name in sorted(expected)]
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "-R",
                REPO,
                "--verify-tag",
                "--draft",
                "--title",
                f"Stake Mirrors Ping {tag}",
                "--notes-file",
                str(notes),
                *files,
            ],
            check=True,
        )
        release = json.loads(output("gh", "api", f"repos/{REPO}/releases/tags/{tag}"))
        if not release["draft"] or {a["name"] for a in release["assets"]} != expected:
            raise SystemExit("Draft asset verification failed; leave draft unpublished")
        print(
            "Draft prepared and assets verified. No tag created and no release published."
        )


if __name__ == "__main__":
    main()
