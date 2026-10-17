# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for HRAgents Agent Server with PEP 420 (implicit namespace) layout.
"""

from pathlib import Path
import os
import site
import sys
from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    collect_data_files,
    copy_metadata,
)

# GNU strip on Windows PE files (notably python3XX.dll) can corrupt the binary
# and cause LoadLibrary to fail at runtime with "Invalid access to memory location".
IS_WINDOWS = sys.platform == "win32"

# Optional Vertex AI bundle. The default build stays lean; install the
# vertex extra first, or pass ENABLE_VERTEX=1 to the Docker build,
# when the binary should support vertex_ai/* partner models.
import importlib.util as _vertex_importlib_util

_VERTEX_AVAILABLE = _vertex_importlib_util.find_spec("vertexai") is not None

_vertex_pkgs = (
    "vertexai",
    "google.cloud.aiplatform",
    "google.cloud.aiplatform_v1",
    "google.cloud.aiplatform_v1beta1",
    "google.cloud.bigquery",
    "google.cloud.storage",
    "google.cloud.resourcemanager",
    "google.api_core",
    "google.auth",
    "google.rpc",
    "google.genai",
    "proto",
    "grpc_status",
)
_vertex_datas = []
_vertex_binaries = []
_vertex_hiddenimports = []
if _VERTEX_AVAILABLE:
    for _pkg in _vertex_pkgs:
        _d, _b, _h = collect_all(_pkg)
        _vertex_datas.extend(_d)
        _vertex_binaries.extend(_b)
        _vertex_hiddenimports.extend(_h)
    # google.rpc.status_pb2 is a gRPC proto stub imported dynamically; only pin
    # it when the SDK is actually present.
    _vertex_hiddenimports.append("google.rpc.status_pb2")
else:
    print(
        "[agent-server.spec] vertexai not installed; "
        "skipping Vertex AI bundle collection. "
        "Install the vertex extra before building to include it."
    )

# Get the project root directory (current working directory when running PyInstaller)
project_root = Path.cwd()
# The project is a single flattened package at the repo root (PEP 420).
PATHEX = [
    project_root,
]

# Entry script for the agent server (runtime/server/__main__.py)
ENTRY = str(project_root / "runtime" / "server" / "__main__.py")

a = Analysis(
    [ENTRY],
    pathex=PATHEX,
    binaries=[
        # Vertex AI SDK binaries (collected via collect_all above)
        *_vertex_binaries,
    ],
    datas=[
        # Third-party packages that ship data
        *collect_data_files("tiktoken"),
        *collect_data_files("tiktoken_ext"),
        *collect_data_files("litellm"),
        *collect_data_files("fastmcp"),
        *collect_data_files("mcp"),

        # HRAgents prompt templates
        *collect_data_files("context.condenser", includes=["prompts/*.j2"]),
        *collect_data_files("context.prompts", includes=["templates/*.j2"]),

        # Built-in subagent definitions consumed by register_builtins_agents()
        # at agent-server startup. Without these, the registry stays empty in
        # PyInstaller builds and downstream clients see an unpopulated
        # task_tool_set description.
        *collect_data_files("tools.preset", includes=["subagents/*.md"]),

        # Package metadata for importlib.metadata
        *copy_metadata("HRAgent"),
        *copy_metadata("fastmcp"),
        *copy_metadata("litellm"),

        # Vertex AI SDK datas (collected via collect_all above)
        *_vertex_datas,
    ],
    hiddenimports=[
        # Pull all first-party modules (PEP 420 safe once pathex is correct)
        *collect_submodules("core"),
        *collect_submodules("context"),
        *collect_submodules("models"),
        *collect_submodules("tools"),
        *collect_submodules("plugins"),
        *collect_submodules("skills"),
        *collect_submodules("subagents"),
        *collect_submodules("mcp_integration"),
        *collect_submodules("security"),
        *collect_submodules("utilities"),
        *collect_submodules("configuration"),
        *collect_submodules("runtime"),
        *collect_submodules("memory"),

        # Third-party dynamic imports
        *collect_submodules("tiktoken"),
        *collect_submodules("tiktoken_ext"),
        *collect_submodules("litellm"),
        *collect_submodules("fastmcp"),
        # rich._unicode_data.unicodeX_Y_Z is imported dynamically based on
        # unicodedata.unidata_version (e.g. unicode17_0_0 on Python 3.13).
        *collect_submodules("rich"),

        # Vertex AI SDK hidden imports (collected via collect_all above; empty
        # if the vertex extra is not installed in the build env).
        *_vertex_hiddenimports,

        # mcp subpackages used at runtime (avoid CLI)
        "mcp.types",
        "mcp.client",
        "mcp.server",
        "mcp.shared",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim size
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "notebook",
        # Exclude mcp CLI parts that pull in typer/extra deps
        "mcp.cli",
        "mcp.cli.cli",
    ],
    noarchive=False,
    # IMPORTANT: don't use optimize=2 (-OO); it strips docstrings needed by parsers (e.g., PLY/bashlex)
    optimize=0,
)

# Remove system libraries that must come from the runtime image, not the builder.
# The PyInstaller binary extracts to /tmp/_MEI*/ and sets LD_LIBRARY_PATH there.
# Child processes (e.g. tmux) inherit this and pick up the bundled libs instead
# of the runtime's system libs, causing version mismatches:
#  - libgcc_s.so: builder may lack GCC_14.0 symbols the runtime expects
#  - libtinfo/libncurses: builder's ncurses is older than runtime's tmux expects
_EXCLUDE_LIB_PREFIXES = ('libgcc_s.so', 'libtinfo.so', 'libncurses')
a.binaries = [x for x in a.binaries if not x[0].startswith(_EXCLUDE_LIB_PREFIXES)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HRAgent-agent-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=not IS_WINDOWS,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
