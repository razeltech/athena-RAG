from fastapi import APIRouter
from pydantic import BaseModel

from app.api.auth import create_token


class LoginRequest(BaseModel):
    username: str
    password: str


router = APIRouter()


@router.post("/auth/login")
async def login(req: LoginRequest):
    # DEV ONLY: accepts any credentials and issues a token for a default org.
    # TODO (Phase 1): replace with real user lookup + password verification
    # against the `users` table, and real org assignment. See docs/PLAN.md.
    org_id = "org_default"
    token = create_token(subject=req.username, org_id=org_id)
    return {"access_token": token, "token_type": "bearer", "org_id": org_id}
