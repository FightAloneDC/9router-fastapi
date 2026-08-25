"""Route registration tests for provider connection endpoints."""

from fastapi.routing import APIRoute

from app.main import app


def test_provider_model_routes_are_registered():
    """Provider model fetch and clear routes must be mounted."""
    routes = {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert ("/providers/{conn_id}/models", "GET") in routes
    assert ("/providers/{conn_id}/models", "DELETE") in routes
