from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.schemas.user import UserLogin, Token
from src.services.user_service import get_user_by_username, verify_password
from src.utils.helpers import create_access_token

router = APIRouter()

@router.post("/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """登录：直接匹配数据库 users 表中的用户，成功后返回 access token。
    token 使用 HS256 签名，前端拿到后以 Authorization: Bearer <token> 放入请求头。
    """
    user = get_user_by_username(db, payload.username)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户不可用")

    # 签发包含用户基础信息的令牌（最少包含 sub=user_id 与 username）
    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
    })
    # 返回原始数据，统一封装由默认响应类处理
    return {"access_token": token, "token_type": "bearer"}