"""Runtime patches for containerized ADK dev UI.

Python automatically imports `sitecustomize` (if available on `sys.path`) on
startup. We use that hook to apply small compatibility patches without
modifying third-party packages.
"""

from __future__ import annotations


def _patch_mcp_client_session_for_pydantic() -> None:
    """Ensure Pydantic can generate a schema for MCP's `ClientSession`.

    Some ADK Web / FastAPI builds attempt to include `mcp.client.session.ClientSession`
    in OpenAPI models. Pydantic v2 requires a core schema hook for unknown types.

    This patch is intentionally permissive: we treat the type as `Any` for schema
    generation purposes.
    """

    try:
        from mcp.client.session import ClientSession

        if hasattr(ClientSession, "__get_pydantic_core_schema__"):
            return

        from pydantic_core import core_schema

        def _get_pydantic_core_schema(cls, _source_type, _handler):
            return core_schema.any_schema()

        ClientSession.__get_pydantic_core_schema__ = classmethod(_get_pydantic_core_schema)  # type: ignore[attr-defined]
    except Exception:
        # Best-effort only.
        return


_patch_mcp_client_session_for_pydantic()


def _patch_types_generic_alias_for_pydantic() -> None:
    """Allow Pydantic to schema-generate `types.GenericAlias`.

    Some dependency combinations end up exposing `types.GenericAlias` (the type
    behind expressions like `list[int]`) directly in OpenAPI models.
    """

    try:
        import types

        if hasattr(types.GenericAlias, "__get_pydantic_core_schema__"):
            return

        from pydantic_core import core_schema

        def _get_pydantic_core_schema(cls, _source_type, _handler):
            return core_schema.any_schema()

        types.GenericAlias.__get_pydantic_core_schema__ = classmethod(_get_pydantic_core_schema)  # type: ignore[attr-defined]
    except Exception:
        return


_patch_types_generic_alias_for_pydantic()
