"""Vercel FastAPI entrypoint.

Vercel resolves custom entrypoints from files in the repository before loading
the installed application package, so this root module exposes the packaged app.
"""

from policy_signal_map.app import app

__all__ = ["app"]
