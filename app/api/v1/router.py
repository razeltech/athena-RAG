from fastapi import APIRouter

from app.api.v1 import auth_routes, chat, conversations, documents, health, personas

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth_routes.router, tags=["auth"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(conversations.router, tags=["conversations"])
api_router.include_router(personas.router, tags=["personas"])
api_router.include_router(chat.router, tags=["chat"])
