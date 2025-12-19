from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List

from src.db.session import get_db
from src.schemas.chat import ChatSessionCreate, ChatSessionRead, ChatMessageCreate, ChatMessageRead
from src.services.chat_service import (
    create_chat_session,
    get_chat_session,
    list_chat_sessions,
    add_message,
    list_messages,
)
from src.api.dependencies import get_current_user_id

router = APIRouter()

@router.post("/chat/sessions", response_model=ChatSessionRead)
def create_session_endpoint(payload: ChatSessionCreate, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """创建一个聊天会话（需要登录）。默认将会话归属当前用户。"""
    if payload.user_id is None:
        payload.user_id = current_user_id
    session = create_chat_session(db, payload)
    # 返回包含空消息列表的会话
    session.messages = []
    return session

@router.get("/chat/sessions", response_model=List[ChatSessionRead])
def list_sessions_endpoint(db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """按当前用户列出会话（需要登录）。"""
    sessions = list_chat_sessions(db, user_id=current_user_id)
    # 带消息返回（可按需简化为不返回消息，仅返回基础信息）
    for s in sessions:
        s.messages = list_messages(db, s.id)
    return sessions

@router.post("/chat/sessions/{session_id}/messages", response_model=ChatMessageRead)
def add_message_endpoint(session_id: int, payload: ChatMessageCreate, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """在指定会话中追加一条消息（需要登录）。若会话归属某用户，则必须为当前用户。"""
    session = get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id is not None and session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权操作该会话")
    msg = add_message(db, session_id, payload)
    return msg

@router.get("/chat/sessions/{session_id}/messages", response_model=List[ChatMessageRead])
def list_messages_endpoint(session_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """获取指定会话的全部消息（需要登录）。若会话归属某用户，则必须为当前用户。"""
    session = get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id is not None and session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权查看该会话")
    return list_messages(db, session_id)

@router.get("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def get_session_detail_endpoint(session_id: int, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """获取聊天详情：返回会话基本信息及消息列表（需要登录）。若会话归属某用户，则必须为当前用户。"""
    session = get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id is not None and session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权查看该会话")
    session.messages = list_messages(db, session_id)
    return session