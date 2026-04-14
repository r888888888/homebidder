"""Profile endpoint: DELETE /api/users/me."""

from fastapi import APIRouter, Depends, Response

from api.auth import current_active_user, fastapi_users
from db.models import User
from db.user_manager import get_user_manager

profile_router = APIRouter()


@profile_router.delete("/users/me", status_code=204)
async def delete_me(
    user: User = Depends(current_active_user),
    user_manager=Depends(get_user_manager),
):
    """Delete the currently authenticated user's account.

    Analyses owned by the user have their user_id set to NULL via the
    ON DELETE SET NULL foreign key constraint, so they remain accessible
    as anonymous analyses.
    """
    await user_manager.delete(user)
    return Response(status_code=204)
