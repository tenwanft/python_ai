from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# 基础用户模式，包含共享字段
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

# 创建用户时的请求模式
class UserCreate(UserBase):
    password: str

# 更新用户时的请求模式
class UserUpdate(UserBase):
    password: Optional[str] = None
    is_active: Optional[bool] = None

# 从数据库读取用户时的响应模式（包含所有字段）
class User(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# 用户查询请求模式
class UserQuery(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None

# 新增：登录请求与令牌响应模型
class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# 新增：用户删除响应模型
class UserDeleteResponse(BaseModel):
    message: str