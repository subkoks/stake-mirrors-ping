"""Deployment checks must not mistake library/linker versions for OS versions."""

from scripts.build_backend import macos_minimums


def test_macos_deployment_parser_ignores_sdk_linker_and_dylib_versions():
    output = """Load command 0
      cmd LC_LOAD_DYLIB
     name /usr/lib/libSystem.B.dylib
          current version 1356.0.0
Load command 1
      cmd LC_BUILD_VERSION
 platform 1
    minos 13.0
      sdk 15.5
   ntools 1
     tool 3
  version 23.1.3
Load command 2
      cmd LC_VERSION_MIN_MACOSX
  version 10.13
      sdk 11.0
"""
    assert macos_minimums(output) == {"13.0", "10.13"}


def test_candidate_accepts_native_linux_package_names(tmp_path, monkeypatch):
    import json

    from scripts import verify_desktop_artifacts

    names = [
        "mac-x64.dmg",
        "mac-x64.zip",
        "mac-arm64.dmg",
        "mac-arm64.zip",
        "win-x64-setup.exe",
        "win-x64-portable.exe",
        "linux-amd64.deb",
        "linux-x86_64.AppImage",
        "linux-x86_64.rpm",
    ]
    for name in names:
        (tmp_path / ("Stake-Mirrors-Ping-2.1.0-" + name)).write_bytes(
            b"x" * 1024 * 1024
        )
    monkeypatch.setattr("sys.argv", ["verify", str(tmp_path)])
    monkeypatch.setattr(
        verify_desktop_artifacts.subprocess, "check_output", lambda *a, **k: "a" * 40
    )
    verify_desktop_artifacts.main()
    manifest = json.loads((tmp_path / "release-manifest.json").read_text())
    assert len(manifest["files"]) == 9
    assert manifest["source_commit"] == "a" * 40
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])
    assert len((tmp_path / "SHA256SUMS.txt").read_text().splitlines()) == 9

    # A wrongly named or extra executable must not silently enter the candidate.
    (tmp_path / "unexpected.exe").write_bytes(b"x")
    import pytest

    with pytest.raises(SystemExit, match="Unexpected release inventory"):
        verify_desktop_artifacts.main()


def test_draft_verification_uses_draft_aware_lookup(monkeypatch):
    import json

    import pytest

    from scripts import prepare_release_draft

    release = {"isDraft": True, "tagName": "v2.1.0", "assets": [{"name": "setup.exe"}]}
    calls = []

    def fake_output(*args):
        calls.append(args)
        return json.dumps(release)

    monkeypatch.setattr(prepare_release_draft, "output", fake_output)
    prepare_release_draft.verify_draft("v2.1.0", {"setup.exe"})
    assert calls[0][:4] == ("gh", "release", "view", "v2.1.0")
    for changed in (
        {"isDraft": False},
        {"tagName": "v9.9.9"},
        {"assets": [{"name": "unexpected.exe"}]},
        {"assets": [{"name": "setup.exe"}, {"name": "setup.exe"}]},
    ):
        original = release.copy()
        release.update(changed)
        with pytest.raises(SystemExit, match="Draft asset verification failed"):
            prepare_release_draft.verify_draft("v2.1.0", {"setup.exe"})
        release.clear()
        release.update(original)
