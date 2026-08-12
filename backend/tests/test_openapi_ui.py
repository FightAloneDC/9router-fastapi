"""OpenAPI UI is exposed only when DEBUG is true."""

from app.openapi_ui import openapi_ui_kwargs


def test_openapi_enabled_when_debug():
    kw = openapi_ui_kwargs(True)
    assert kw["docs_url"] == "/docs"
    assert kw["redoc_url"] == "/redoc"
    assert kw["openapi_url"] == "/openapi.json"


def test_openapi_disabled_when_not_debug():
    kw = openapi_ui_kwargs(False)
    assert kw["docs_url"] is None
    assert kw["redoc_url"] is None
    assert kw["openapi_url"] is None
