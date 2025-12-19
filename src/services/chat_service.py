from sqlalchemy.orm import Session
from typing import Optional, List
from src.models.chat import ChatSession, ChatMessage
from src.schemas.chat import ChatSessionCreate, ChatMessageCreate

# 会话

# 基于首条用户问题生成会话标题（截取前 max_len 个字符，移除多余空白）
def _generate_session_title(content: str, max_len: int = 30) -> str:
    txt = (content or "").strip()
    first_line = txt.splitlines()[0] if txt else ""
    normalized = " ".join(first_line.split())
    if not normalized:
        return "新会话"
    if len(normalized) <= max_len:
        return normalized
    return normalized[:max_len].rstrip() + "..."


def create_chat_session(db: Session, data: ChatSessionCreate) -> ChatSession:
    session = ChatSession(user_id=data.user_id, title=data.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_chat_session(db: Session, session_id: int) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def list_chat_sessions(db: Session, user_id: Optional[int] = None) -> List[ChatSession]:
    q = db.query(ChatSession)
    if user_id is not None:
        q = q.filter(ChatSession.user_id == user_id)
    return q.order_by(ChatSession.updated_at.desc()).all()

# 消息

def add_message(db: Session, session_id: int, data: ChatMessageCreate) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=data.role, content=data.content, model=data.model)
    db.add(msg)
    # 更新会话的更新时间，并在首条用户消息时生成标题
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        # 若标题为空且为用户消息，则用首条用户问题生成标题
        if (not session.title or not session.title.strip()) and data.role == "user":
            session.title = _generate_session_title(data.content)
        # flush 以确保关系更新
        db.flush()
    db.commit()
    db.refresh(msg)
    return msg


def list_messages(db: Session, session_id: int) -> List[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .all()
    )

# 方案C（原表字段）：会话摘要存储在 ChatSession.summary

def get_session_summary_text(db: Session, session_id: int) -> Optional[str]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    return session.summary if session else None


def update_session_summary_text(db: Session, session_id: int, text: Optional[str]) -> Optional[str]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        return None
    session.summary = text
    # summary_updated_at 由 onupdate 自动维护
    db.commit()
    return session.summary