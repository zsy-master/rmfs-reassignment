"""Isolated optional entry points; scientific legacy files are kept unchanged."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

OPTIONAL = Path(__file__).resolve().parent
ROOT = OPTIONAL.parent
sys.path.insert(0, str(ROOT))
from io_utils import sha256
from reproduce import check_assets


def load_legacy(name):
    check_assets()
    lock = json.loads((OPTIONAL / "OPTIONAL_HASHES.json").read_text(encoding="utf-8"))
    for relative, expected in lock.items():
        path = OPTIONAL / relative
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Optional source/reference hash mismatch: {relative}")
    sys.path.insert(0, str(OPTIONAL / "legacy"))
    spec = importlib.util.spec_from_file_location(
        f"legacy_{name}", OPTIONAL / "legacy" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def new_output(path):
    output = path.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Output must be outside protected code/reference folders")
    output.mkdir(parents=True, exist_ok=False)
    return output
