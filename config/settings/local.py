"""Desarrollo local y tests. Requiere DATABASE_URL apuntando a un PostgreSQL local."""

import os

os.environ.setdefault("SECRET_KEY", "solo-desarrollo-local-no-usar-en-produccion")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1")

from .base import *  # noqa: E402,F403
