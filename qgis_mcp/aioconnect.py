"""AiConnect adapter for the QGIS MCP fork (integration layer — upstream
tools are NOT modified; everything AiConnect-specific lives here).

Two responsibilities, reusing the shared Python SDK (connectors/sdk/python):
  1. License gate — startup + per-call check of the short-lived signed token
     the Process Manager injects via MCP_LICENSE_TOKEN (manifest token_env_var).
  2. Response envelope — every registered tool's return value is wrapped in
     the tool-response envelope (ok/fail) centrally at registration time, so
     none of the ~118 upstream tools need per-tool edits.

Env-gated integration points (set by the gateway/bridge):
  AICONNECT_ENABLE=1        — actually install the license gate + envelope wrap
                              (standalone upstream use stays untouched)
  MCP_LICENSE_TOKEN         — the token to validate
  JWT_SECRET                — token signing secret (default matches gateway dev)
"""
import asyncio
import functools
import json
import os
import sys
from pathlib import Path

# make the shared SDK importable: AICONNECT_SDK_PATH env wins (installed
# AiConnect SDK, keeps the public fork IP-free); else monorepo-relative
# fallback (connectors/<category>/<id>/qgis_mcp/aioconnect.py).
_env_sdk = os.environ.get("AICONNECT_SDK_PATH", "")
_SDK = Path(_env_sdk).resolve() if _env_sdk else Path(__file__).resolve().parents[3] / "sdk" / "python"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from mcp_license_sdk import LicenseError, LicenseValidator, fail, ok  # noqa: E402
from mcp_license_sdk import interception  # noqa: E402

CONNECTOR_ID = "qgis-mcp"


def _enabled() -> bool:
    return os.environ.get("AICONNECT_ENABLE", "") == "1"


def _validate() -> dict:
    """Validate the PM-injected token AND its connector binding.

    The Process Manager mints tokens with subject `connector:<id>` and
    entitlements `[<id>]` (auth.rs::mint). Signature + expiry are checked
    by the SDK; binding is asserted here so a token minted for another
    connector can never authorize this one.
    """
    claims = LicenseValidator(os.environ.get("JWT_SECRET", "dev-secret-change-me")).ensure_licensed()
    if claims.get("sub") != f"connector:{CONNECTOR_ID}":
        raise LicenseError(f"token not bound to {CONNECTOR_ID}")
    scopes = claims.get("entitlements") or claims.get("scopes") or []
    if CONNECTOR_ID not in scopes:
        raise LicenseError(f"token lacks scope {CONNECTOR_ID}")
    return claims


def ensure_licensed() -> None:
    """Startup gate: refuses to boot without a valid bound license token."""
    if not _enabled():
        return
    _validate()


def _wrap_result(r):
    """Envelope any tool return value (plan §5 tool-response schema)."""
    if isinstance(r, str):
        text = r.strip()
        if text:
            try:
                data = json.loads(text)
                return json.dumps(ok(data))
            except json.JSONDecodeError:
                return json.dumps(fail("TOOL_ERROR", "non-JSON tool output"))
        return json.dumps(ok({"result": ""}))
    return json.dumps(ok(r))


def _wrap(fn):
    """Per-call license recheck + envelope wrap around one tool function.

    functools.wraps preserves the ORIGINAL signature via __wrapped__: FastMCP
    3.x derives the input model and ctx injection from inspect.signature at
    call/registration time — a bare (*args, **kwargs) wrapper makes it pass
    the arguments object as a string (DictModel validation error).
    """
    @functools.wraps(fn)
    async def _w(*args, **kwargs):
        if not _enabled():
            return await _call(fn, args, kwargs)
        try:
            _validate()  # per-call recheck (cheap HS256) + binding
            result = await _call(fn, args, kwargs)
            return _wrap_result(result)
        except LicenseError as e:
            # license failure is a structured envelope too, never a raise
            return json.dumps(fail("LICENSE", str(e)))
        except Exception as e:  # structured error, not a raw exception
            return json.dumps(fail("TOOL_ERROR", str(e)))
    return _w


async def _call(fn, args, kwargs):
    if asyncio.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    return fn(*args, **kwargs)


def wrap_tools(mcp) -> int:
    """Legacy per-tool fn swap (FastMCP <3.x / fastmcp 1.x fallback).

    Do NOT use on FastMCP 3.4.7: replacing tool.fn keeps the frozen
    fn_metadata output model, so a wrapped JSON-string return fails
    structured-output validation (DictModel input_type=str). Prefer
    install_call_interceptor on 3.x.
    """
    if not _enabled():
        return 0
    wrapped = 0
    # version-tolerant discovery: FastMCP (1.x) exposes mcp._tool_manager._tools;
    # MCPServer (2.x) may differ. Accept either a manager object holding a
    # registry, or a bare registry dict.
    registry = None
    for candidate in (getattr(mcp, "_tool_manager", None), getattr(mcp, "_tools", None)):
        if candidate is None:
            continue
        reg = getattr(candidate, "_tools", None) or getattr(candidate, "tools", None)
        if isinstance(reg, dict):
            registry = reg
            break
        if isinstance(candidate, dict) and candidate:
            registry = candidate
            break
    if registry is None:
        print("aioconnect: tool manager not found — envelope wrap skipped", file=sys.stderr)
        return 0
    for name, tool in list(registry.items()):
        fn = getattr(tool, "fn", None) or tool
        if fn is None or getattr(fn, "_aioconnect_wrapped", False):
            continue
        wrapped_fn = _wrap(fn)
        wrapped_fn._aioconnect_wrapped = True
        if hasattr(tool, "fn"):
            tool.fn = wrapped_fn
        else:
            registry[name] = wrapped_fn
        wrapped += 1
    return wrapped


def install_call_interceptor(mcp) -> bool:
    """Envelope tools/call via the shared SDK helper (mcp_license_sdk.
    interception) — low-level call_tool re-registration on the mcp-SDK
    FastMCP class; tools stay untouched (fixes the FastMCP 3.4.7
    wrapped-call failure). Returns True when installed; False → caller
    falls back to the legacy per-tool wrap (fastmcp <3.x)."""
    if not _enabled():
        return False
    installed = interception.install_call_interceptor(mcp, _validate, _wrap_result)
    if not installed:
        print("aioconnect: call interceptor not installed — falling back to wrap_tools", file=sys.stderr)
    return installed
