"""Deterministic self-contained Lua bundle for Observatory experiments."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ControllerBundleError(RuntimeError):
    """Raised when controller sources cannot form a safe Lua bundle."""


def _long_bracket(source: str) -> str:
    for equals_count in range(1, 33):
        equals = "=" * equals_count
        closing = f"]{equals}]"
        if closing not in source:
            return f"[{equals}[\n{source}]{equals}]"
    raise ControllerBundleError("source defeats bounded Lua quoting")


def render_controller_bundle(
    runtime_source: str,
    controller_source: str,
) -> str:
    """Return one inert Lua artifact containing the exact two modules."""
    if type(runtime_source) is not str or not runtime_source:
        raise ControllerBundleError("runtime source must be non-empty text")
    if type(controller_source) is not str or not controller_source:
        raise ControllerBundleError("controller source must be non-empty text")
    try:
        runtime_source.encode("utf-8", errors="strict")
        controller_source.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ControllerBundleError("controller source is not valid UTF-8") from exc
    runtime_literal = _long_bracket(runtime_source)
    controller_literal = _long_bracket(controller_source)
    return (
        "-- Generated ITB Observatory controller bundle; source-only and inert.\n"
        "local runtime_source = "
        + runtime_literal
        + "\nlocal controller_source = "
        + controller_literal
        + "\nlocal runtime_chunk, runtime_error = loadstring("
        'runtime_source, "@observatory_trace.lua")\n'
        "if not runtime_chunk then error(runtime_error) end\n"
        "local controller_chunk, controller_error = loadstring("
        'controller_source, "@observatory_controller.lua")\n'
        "if not controller_chunk then error(controller_error) end\n"
        "local runtime_module = runtime_chunk()\n"
        "local controller_module = controller_chunk()\n"
        "return controller_module.bind_runtime(runtime_module)\n"
    )


def controller_bundle_sha256(bundle: str) -> str:
    if type(bundle) is not str:
        raise ControllerBundleError("controller bundle must be text")
    try:
        encoded = bundle.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ControllerBundleError("controller bundle is not valid UTF-8") from exc
    return hashlib.sha256(encoded).hexdigest()


def build_controller_bundle(
    *,
    runtime_path: Path,
    controller_path: Path,
) -> str:
    """Read explicit source paths and render their deterministic bundle."""
    try:
        runtime_source = Path(runtime_path).read_bytes().decode(
            "utf-8", errors="strict"
        )
        controller_source = Path(controller_path).read_bytes().decode(
            "utf-8", errors="strict"
        )
    except (OSError, UnicodeError) as exc:
        raise ControllerBundleError(
            f"cannot read controller source: {exc}"
        ) from exc
    return render_controller_bundle(runtime_source, controller_source)
