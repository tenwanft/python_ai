from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
def health_check():
    """
    健康检查端点
    用于验证应用程序是否正常运行
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "API服务运行正常"
    }