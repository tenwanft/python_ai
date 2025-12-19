from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.utils.helpers import decode_token, TokenError
from src.services.user_service import get_user

security_scheme = HTTPBearer(auto_error=False)


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> int:
    """从 Authorization: Bearer <token> 中解析并返回当前用户ID（int）。
    若令牌无效或过期，抛出 401。
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供有效的认证凭证")
    token = credentials.credentials
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌缺少标识")
        return int(sub)
    except TokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌解析失败")


def get_current_user(dep_user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """根据解析出的用户ID获取数据库中的用户实体。若不存在则 401。"""
    user = get_user(db, dep_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已删除")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户不可用")
    return user