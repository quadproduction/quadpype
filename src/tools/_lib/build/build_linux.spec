# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys

# Ensure PyInstaller finds all dependencies
hiddenimports = collect_submodules('quadpype') + collect_submodules('igniter') + \
    collect_submodules("aiohttp") + \
    collect_submodules("aiohttp_json_rpc") + \
    collect_submodules("acre") + \
    collect_submodules("appdirs") + \
    collect_submodules("blessed") + \
    collect_submodules("bson") + \
    collect_submodules("bson.json_util") + \
    collect_submodules("coolname") + \
    collect_submodules("clique") + \
    collect_submodules("click") + \
    collect_submodules("dns") + \
    collect_submodules("ftrack_api") + \
    collect_submodules("arrow") + \
    collect_submodules("httplib2") + \
    collect_submodules("shotgun_api3") + \
    collect_submodules("gazu") + \
    collect_submodules("googleapiclient") + \
    collect_submodules("jsonschema") + \
    collect_submodules("keyring") + \
    collect_submodules("log4mongo") + \
    collect_submodules("pathlib2") + \
    collect_submodules("PIL") + \
    collect_submodules("pyblish") + \
    collect_submodules("pynput") + \
    collect_submodules("pymongo") + \
    collect_submodules("qtpy") + \
    collect_submodules("qtawesome") + \
    collect_submodules("speedcopy") + \
    collect_submodules("six") + \
    collect_submodules("semver") + \
    collect_submodules("wsrpc_aiohttp") + \
    collect_submodules("jinxed") + \
    collect_submodules("enlighten") + \
    collect_submodules("slackclient") + \
    collect_submodules("requests") + \
    collect_submodules("pysftp") + \
    collect_submodules("dropbox") + \
    collect_submodules("cryptography") + \
    collect_submodules("opentimelineio") + \
    collect_submodules("colorama") + \
    collect_submodules("fastapi") + \
    collect_submodules("uvicorn") + \
    collect_submodules("htmllistparse") + \
    collect_submodules("lief") + \
    collect_submodules("jedi") + \
    collect_submodules("jinja2") + \
    collect_submodules("markupsafe") + \
    collect_submodules("wheel") + \
    collect_submodules("enlighten") + \
    collect_submodules("toml")

a = Analysis(
    ['start.py'],
    pathex=['.', os.path.abspath('quadpype'), os.path.abspath('igniter')],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_console = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='quadpype_console',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

exe_gui = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='quadpype_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_console,
    a.scripts,
    a.binaries,
    a.datas,
    exe_gui,
    a.scripts,
    a.binaries,
    a.datas,
    name='exe_quadpype'
)
