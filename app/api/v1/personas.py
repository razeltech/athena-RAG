from fastapi import APIRouter

from app.services.modes import list_modes
from app.services.personas import list_personas

router = APIRouter()


@router.get("/personas")
async def get_personas() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "description": p.description}
        for p in list_personas()
    ]


@router.get("/modes")
async def get_modes() -> list[dict]:
    return [
        {"id": m.id, "name": m.name, "description": m.description}
        for m in list_modes()
    ]
