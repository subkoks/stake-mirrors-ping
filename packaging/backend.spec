# Build each architecture with its native Python; never cross-package a backend.
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = [], [], []
for package in ('curl_cffi', 'certifi', 'pydantic'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
for package in ('stake-mirrors-ping', 'aiohttp', 'certifi', 'curl-cffi', 'pydantic', 'PyYAML', 'rich', 'python-dotenv'):
    datas += copy_metadata(package)
a = Analysis([ENTRY], pathex=[ROOT], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=['pytest', 'ruff', 'mypy', 'pip', 'setuptools'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='stake-backend',
          console=True, upx=False, strip=False)
coll = COLLECT(exe, a.binaries, a.datas, name='stake-backend', upx=False, strip=False)
