from fastapi import APIRouter
from src.api.v1.endpoints.health import router as health_router
from src.api.v1.endpoints.product import router as product_router
from src.api.v1.endpoints.user import router as user_router
from src.api.v1.endpoints.data_stream import router as llm_router
from src.api.v1.endpoints.chat import router as chat_router
from src.api.v1.endpoints.auth import router as auth_router
from src.api.v1.endpoints.storage import router as storage_router
from src.api.v1.endpoints.paper import router as paper_router
from src.api.v1.endpoints.paper_analysis import router as paper_analysis_router
from src.api.v1.endpoints.embedding import router as embedding_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["healthcheck"])  
api_router.include_router(product_router, tags=["products"])  
api_router.include_router(user_router, tags=["users"])  
api_router.include_router(llm_router, tags=["llm"])  
api_router.include_router(chat_router, tags=["chat"])  
api_router.include_router(auth_router, tags=["auth"])  
api_router.include_router(storage_router, tags=["storage"])  
api_router.include_router(paper_router, tags=["paper"])  
api_router.include_router(paper_analysis_router, tags=["paper_analysis"])  
api_router.include_router(embedding_router, tags=["embedding"])
