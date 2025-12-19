from sqlalchemy.orm import Session
from src.models.user import User
from src.schemas.user import UserCreate, UserUpdate
from passlib.context import CryptContext

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, user_id: int) -> User:
    """根据ID获取用户"""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> User:
    """根据用户名获取用户"""
    return db.query(User).filter(User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """获取用户列表"""
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    """创建新用户"""
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user: UserUpdate) -> User:
    """更新用户信息"""
    db_user = get_user(db, user_id)
    if db_user:
        if user.username: 
            db_user.username = user.username
        if user.email: 
            db_user.email = user.email
        if user.full_name: 
            db_user.full_name = user.full_name
        if user.password: 
            db_user.hashed_password = get_password_hash(user.password)
        if user.is_active is not None: 
            db_user.is_active = user.is_active
        
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> bool:
    """删除用户"""
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False