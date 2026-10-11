from fastapi.routing import APIRoute

from mc_api.main import app


def test_every_route_lives_in_a_router_module():
    # include_router keeps lazy _IncludedRouter objects; the router's route paths already carry its prefix.
    flat = [
        x
        for r in app.routes
        for x in (r.original_router.routes if hasattr(r, "original_router") else [r])
    ]
    routes = [r for r in flat if isinstance(r, APIRoute)]
    assert routes
    assert all(r.endpoint.__module__.startswith("mc_api.routers.") for r in routes)
    paths = {r.path for r in routes}
    assert {"/health", "/auth/login", "/me", "/users/{user_id}"} <= paths


def test_shared_dependencies_module():
    from mc_api.dependencies import get_current_user, get_scope

    assert callable(get_current_user) and callable(get_scope)
