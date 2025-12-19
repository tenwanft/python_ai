from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Iterator

from langchain_ollama import ChatOllama

from sqlalchemy.orm import Session
from src.db.session import get_db
from src.schemas.chat import ChatMessageCreate, ChatSessionCreate
from src.services.chat_service import create_chat_session, get_chat_session, add_message, list_messages, get_session_summary_text, update_session_summary_text
from src.api.dependencies import get_current_user_id
import json

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    model: Optional[str] = None  # 默认使用 qwen32b（可传 qwen2.5:3b 验证）
    temperature: Optional[float] = 0.2
    num_predict: Optional[int] = 1024
    stream: Optional[bool] = False
    # 新增：会话与用户信息，用于将消息写入数据库
    session_id: Optional[int] = None
    user_id: Optional[int] = None


def _build_messages(messages: Optional[List[Dict[str, str]]]) -> Optional[List[tuple]]:
    if not messages:
        return None
    converted = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if not role or content is None:
            continue
        converted.append((role, content))
    return converted

# 基于模型生成简短会话标题（中文，尽量不超过 20-30 字，无标点/引号）
def _generate_title_with_llm(text: str, model: Optional[str], temperature: Optional[float]) -> Optional[str]:
    if not text:
        return None
    m = model or "qwen2.5:3b"
    try:
        llm = ChatOllama(model=m, temperature=temperature or 0.2, num_predict=64)
        prompt = (
            "请将下面的用户问题概括为一个简短的中文标题，不超过30字，不要包含标点或引号：\n" + text
        )
        ai = llm.invoke(prompt)
        title = getattr(ai, "content", str(ai)).strip()
        title = " ".join(title.splitlines()).strip(" “”\"'。.!?：:；;，,")
        if not title:
            return None
        return title[:30]
    except Exception:
        return None

# 方案C：从会话摘要构建上下文（将摘要作为系统消息置于最前），再拼接最近 N 条历史消息。
def _build_context_with_summary(db: Session, session_id: int, window_size: int) -> List[Dict[str, str]]:
    db_msgs = list_messages(db, session_id)
    summary_text = get_session_summary_text(db, session_id)
    prefix = db_msgs[-window_size:]
    combined: List[Dict[str, str]] = []
    if summary_text:
        combined.append({"role": "system", "content": f"对话摘要：{summary_text}"})
    combined.extend({"role": m.role, "content": m.content} for m in prefix)
    return combined

# 方案C：用模型更新会话摘要（基于旧摘要与最新一轮对话）。
def _update_session_summary_with_llm(db: Session, session_id: int, prev_summary: Optional[str], user_text: str, assistant_text: str, model: Optional[str], temperature: Optional[float]):
    try:
        m = model or "qwen2.5:3b"
        llm = ChatOllama(model=m, temperature=temperature or 0.2, num_predict=256)
        prompt = (
            "你是对话摘要助手。请基于现有摘要和最近一轮对话更新会话摘要，保持简洁、中文、包含关键事实、用户意图与已达成结论，不要包含无关细节。\n"
            f"现有摘要：\n{prev_summary or '（无）'}\n\n"
            f"最近对话：\n用户：{user_text}\n助手：{assistant_text}\n\n"
            "请输出更新后的完整摘要。"
        )
        ai = llm.invoke(prompt)
        new_summary = getattr(ai, "content", str(ai)).strip()
        update_session_summary_text(db, session_id, new_summary)
    except Exception:
        # 摘要更新失败时不影响主流程
        pass


def _sse_stream_generator(req: ChatRequest, db: Session, session_id: int, user_message_id: int, user_text: str) -> Iterator[str]:
    """将模型流式输出封装为 SSE 事件，只发送纯文本增量，不包含任何 meta/done 等 JSON。
    在完成后将助手消息写入数据库并更新会话摘要，但不对外发送 ID。
    """
    model = req.model or "qwen2.5:3b"
    llm = ChatOllama(
        model=model,
        temperature=req.temperature or 0.2,
        num_predict=req.num_predict or 256,
    )
    msgs = _build_messages(req.messages)
    final_text = ""
    stream = llm.stream(msgs if msgs else (req.prompt or ""))
    for chunk in stream:
        text = getattr(chunk, "content", "")
        if text:
            final_text += text
            sse_payload = json.dumps({"event": "delta", "data": text}, ensure_ascii=False)
            yield f"data: {sse_payload}\n\n"
    # 流式结束后，落库助手完整消息并更新摘要
    try:
        add_message(db, session_id, ChatMessageCreate(role="assistant", content=final_text, model=model))
        prev_summary = get_session_summary_text(db, session_id)
        _update_session_summary_with_llm(db, session_id, prev_summary, user_text, final_text, model, req.temperature)
    except Exception:
        pass
    # 显式发送完成事件，便于客户端识别结束
    done_payload = json.dumps({"event": "done", "data": "[DONE]"}, ensure_ascii=False)
    yield f"data: {done_payload}\n\n"


# 上下文窗口大小：每次调用时自动拼接最近 N 条历史消息
CONTEXT_WINDOW_SIZE = 12

@router.post("/llm/generate")
def llm_generate(req: ChatRequest):
    """非流式生成接口：支持 prompt 或 messages。
    默认模型为 qwen2.5:3b；如需快速验证可传 qwen2.5:3b。
    """
    model = req.model or "qwen2.5:3b"
    try:
        llm = ChatOllama(
            model=model,
            temperature=req.temperature or 0.2,
            num_predict=req.num_predict or 256,
        )
        msgs = _build_messages(req.messages)
        if msgs:
            ai = llm.invoke(msgs)
        elif req.prompt:
            ai = llm.invoke(req.prompt)
        else:
            raise HTTPException(status_code=400, detail="必须提供 prompt 或 messages")
        return {"content": getattr(ai, "content", str(ai)), "model": model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用模型失败: {e}")


@router.post("/llm/chat")
def llm_chat(req: ChatRequest, db: Session = Depends(get_db), current_user_id: int = Depends(get_current_user_id)):
    """统一接口（需要登录）：根据 req.stream 返回流式或非流式数据（流式为 SSE）。
    在调用模型的同时，将用户消息与助手回复写入数据库，并维护会话摘要（方案C）。
    默认模型为 qwen2.5:3b；如需快速验证可传 qwen2.5:3b。
    若未提供 user_id，则默认写入当前登录用户。
    """
    if not req.prompt and not req.messages:
        raise HTTPException(status_code=400, detail="必须提供 prompt 或 messages")

    # 使用当前用户作为归属
    if req.user_id is None:
        req.user_id = current_user_id

    # 解析用户消息内容（优先取 messages 中最后一个 user 消息，否则取 prompt）
    msgs = _build_messages(req.messages)
    user_content: Optional[str] = None
    if msgs:
        for role, content in reversed(msgs):
            if role == "user":
                user_content = content
                break
    if not user_content:
        user_content = req.prompt
    if not user_content:
        raise HTTPException(status_code=400, detail="无法解析用户输入内容")

    # 准备会话：若无 session_id，则自动创建一个，归属当前用户
    session_id = req.session_id
    if session_id:
        session = get_chat_session(db, session_id)
        if not session:
            session = create_chat_session(db, ChatSessionCreate(user_id=req.user_id, title=None))
            session_id = session.id
        else:
            if session.user_id is not None and session.user_id != current_user_id:
                raise HTTPException(status_code=403, detail="无权使用该会话")
    else:
        session = create_chat_session(db, ChatSessionCreate(user_id=req.user_id, title=None))
        session_id = session.id

    # 如果会话没有标题，尝试用模型生成一个标题（在首次写入用户消息之前）
    if (not session.title or not session.title.strip()) and user_content:
        ai_title = _generate_title_with_llm(user_content, req.model, req.temperature)
        if ai_title:
            session.title = ai_title

    # 先落库用户消息
    user_msg = add_message(db, session_id, ChatMessageCreate(role="user", content=user_content, model=req.model))

    # 自动拼接上下文（方案C）：会话摘要 + 最近 N 条消息
    try:
        combined = _build_context_with_summary(db, session_id, CONTEXT_WINDOW_SIZE)
        req.messages = combined
        req.prompt = None
    except Exception:
        pass

    # 流式
    if req.stream:
        return StreamingResponse(_sse_stream_generator(req, db, session_id, user_msg.id, user_content), media_type="text/event-stream")

    # 非流式：调用生成并落库助手消息，然后更新摘要
    result = llm_generate(req)
    ai_text = result.get("content", "")
    add_message(db, session_id, ChatMessageCreate(role="assistant", content=ai_text, model=result.get("model")))
    try:
        prev_summary = get_session_summary_text(db, session_id)
        _update_session_summary_with_llm(db, session_id, prev_summary, user_content, ai_text, result.get("model"), req.temperature)
    except Exception:
        pass
    return {
        "content": result.get("content", ""),
        "model": result.get("model"),
    }
