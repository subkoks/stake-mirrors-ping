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
