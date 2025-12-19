from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from src.schemas.user import User, UserCreate, UserUpdate, UserQuery, UserDeleteResponse
from src.services.user_service import get_user, get_user_by_username, get_users, create_user, update_user, delete_user
from src.db.session import get_db

router = APIRouter()

@router.post("/users", response_model=User)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    """创建新用户"""
    # 检查用户名是否已存在
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    created = create_user(db=db, user=user)
    return created

@router.get("/users", response_model=List[User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取用户列表"""
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """根据ID获取用户信息"""
    db_user = get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return db_user

@router.put("/users/{user_id}", response_model=User)
def update_existing_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """更新用户信息"""
    db_user = update_user(db, user_id=user_id, user=user)
    if db_user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return db_user

@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
def delete_existing_user(user_id: int, db: Session = Depends(get_db)):
    """删除用户"""
    success = delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "用户已成功删除"}

@router.post("/users/query", response_model=User)
def query_user(query: UserQuery, db: Session = Depends(get_db)):
    """查询用户信息接口
    通过用户ID或用户名查询用户详情
    """
    # 验证查询参数
    if not query.user_id and not query.username:
        raise HTTPException(
            status_code=400,
            detail="必须提供user_id或username作为查询条件"
        )

    # 按ID查询
    if query.user_id:
        db_user = get_user(db, user_id=query.user_id)
        if db_user:
            return db_user
        raise HTTPException(status_code=404, detail=f"用户ID {query.user_id} 不存在")

    # 按用户名查询
    if query.username:
        db_user = get_user_by_username(db, username=query.username)
        if db_user:
            return db_user
        raise HTTPException(status_code=404, detail=f"用户名 {query.username} 不存在")