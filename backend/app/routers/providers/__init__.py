"""Provider routes — modular breakdown of the original providers.py.

Re-exports ``router`` so that ``from app.routers.providers import router``
continues to work unchanged.
"""

from app.routers.providers._router import router

# Import all endpoint modules to register their routes on the shared router.
# The order does not matter for FastAPI route registration — FastAPI matches
# by specificity (static before parameterized).
from app.routers.providers import catalog  # noqa: F401
from app.routers.providers import connections  # noqa: F401
from app.routers.providers import models  # noqa: F401
from app.routers.providers import nodes  # noqa: F401
from app.routers.providers import testing  # noqa: F401

__all__ = ["router"]
