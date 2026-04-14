import uuid
import logging
from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from db.models import User

log = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """fastapi-users UserManager with lazy secret resolution."""

    @property
    def reset_password_token_secret(self) -> str:  # type: ignore[override]
        return settings.jwt_secret

    @property
    def verification_token_secret(self) -> str:  # type: ignore[override]
        return settings.jwt_secret

    async def on_after_register(self, user: User, request=None) -> None:
        log.info("User %s registered.", user.id)

    async def on_after_forgot_password(self, user: User, token: str, request=None) -> None:
        # Log the token instead of emailing until an SMTP integration is wired up.
        log.info("Password reset requested for user %s. Token: %s", user.id, token)

    async def on_after_request_verify(self, user: User, token: str, request=None) -> None:
        log.info("Email verification requested for user %s. Token: %s", user.id, token)


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
