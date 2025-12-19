from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str
    
    # 应用配置
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # 腾讯云 COS 配置
    COS_SECRET_ID: Optional[str] = None
    COS_SECRET_KEY: Optional[str] = None
    COS_REGION: Optional[str] = None
    COS_BUCKET: Optional[str] = None
    # 可选：如果有自定义 CDN 域名/静态域名，返回该域名的公开URL
    COS_PUBLIC_DOMAIN: Optional[str] = None

    # Qwen (DashScope OpenAI兼容) 配置
    # 建议在 .env 中设置：QWEN_API_KEY 和（可选）QWEN_API_BASE
    # 若未设置 QWEN_API_BASE，将使用 DashScope 的兼容地址作为默认值
    QWEN_API_KEY: Optional[str] = None
    QWEN_API_BASE: Optional[str] = None

    OPENAI_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 创建全局设置实例
settings = Settings()