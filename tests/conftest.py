"""Pytest configuration: filter third-party deprecation warnings.

Third-party libraries (starlette, anyio, fastapi, httpx) emit deprecation
warnings we cannot fix from our code. These are filtered to 'ignore'
for known unfixable ones. Warnings from our own code (personal_world)
are treated as errors to enforce clean code.
"""

import warnings

# Known unfixable third-party warnings (we cannot change their source)
warnings.filterwarnings("ignore", message=".*httpx.*starlette.*deprecated.*")
warnings.filterwarnings("ignore", message=".*anyio.abc.BlockingPortal.*deprecated.*")
warnings.filterwarnings("ignore", message=".*on_event is deprecated.*")

# Third-party warnings in general (visible but not errors)
warnings.filterwarnings("default", category=DeprecationWarning, module="starlette")
warnings.filterwarnings("default", category=DeprecationWarning, module="anyio")
warnings.filterwarnings("default", category=DeprecationWarning, module="fastapi")
warnings.filterwarnings("default", category=DeprecationWarning, module="httpx")
warnings.filterwarnings("default", category=DeprecationWarning, module="pydantic")
warnings.filterwarnings("default", category=DeprecationWarning, module="uvicorn")
warnings.filterwarnings("default", category=DeprecationWarning, module="h11")
warnings.filterwarnings("default", category=DeprecationWarning, module="h2")
warnings.filterwarnings("default", category=DeprecationWarning, module="sniffio")

# Our code warnings must be clean
warnings.filterwarnings("error", category=DeprecationWarning, module="personal_world")
warnings.filterwarnings("error", category=PendingDeprecationWarning, module="personal_world")
warnings.filterwarnings("error", category=FutureWarning, module="personal_world")
