"""
fastapi-users authentication setup.

Exports:
  fastapi_users       — the FastAPIUsers instance (used in main.py to register routers)
  auth_backend        — JWT Bearer authentication backend
  current_active_user — dependency: raises 401 if request is unauthenticated
  current_optional_user — dependency: returns None if request is unauthenticated
"""
import uuid

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy

from config import settings
from db.models import User
from db.user_manager import get_user_manager

bearer_transport = BearerTransport(tokenUrl="/api/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    # Secret is read lazily at request time so startup failures are clear.
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=86400 * 30)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Use current_active_user where a valid login is required (e.g. profile routes).
current_active_user = fastapi_users.current_user(active=True)

# Use current_optional_user where auth is optional (analyze, history, rate limiter).
# Returns None — never raises 401 — when the request has no token or an invalid token.
current_optional_user = fastapi_users.current_user(active=True, optional=True)
