from src.db.base import Base
from src.db.session import engine

# 创建所有数据库表
def init_db():
    # 延迟导入以避免循环依赖
    from src.models.user import User  # noqa: F401
    from src.models.product import Product  # noqa: F401
    from src.models.chat import ChatSession, ChatMessage  # 新增聊天相关模型  # noqa: F401
    from src.models.paper import PaperAnalysis  # 新增论文解析结果模型  # noqa: F401
    Base.metadata.create_all(bind=engine)

__all__ = ["Base", "engine", "init_db"]