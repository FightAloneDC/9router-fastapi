"""OpenAPI / Swagger UI gating for production."""


def openapi_ui_kwargs(debug: bool) -> dict[str, str | None]:
    if debug:
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
