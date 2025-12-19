from fastapi import APIRouter, HTTPException, Body
from typing import List
from src.core.logger import get_logger

from src.services.embedding_service import (
    split_text_into_chunks,
    get_chroma_store,
    add_text_chunks_to_chroma,
    query_similar_texts,
    create_embedding,
)
from src.utils.helpers import read_online_pdf_text
from langchain_openai import ChatOpenAI
from src.core.config import settings
import os

router = APIRouter()
logger = get_logger("embedding")

@router.post("/embedding/rag_search")
def rag_search_endpoint(
    payload: dict = Body(..., example={
        "query": "用户的提问",
        "pdf_url": "https://agent-1300436343.cos.ap-shanghai.myqcloud.com/uploads/pdf/2025/10/05/b918852f01db4bc8b7182b113adedf42.pdf",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "top_k": 4
    })
):
    """接受用户查询与指定 PDF URL：若该 PDF 尚未入库，则读取、分块并写入默认向量库；随后执行基于该 PDF 的 RAG 相似检索，返回 top-k 片段。"""
    query = payload.get("query")
    pdf_url = payload.get("pdf_url")
    if not query:
        raise HTTPException(status_code=400, detail="query 字段不能为空")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url 字段不能为空")

    chunk_size: int = int(payload.get("chunk_size", 1000))
    chunk_overlap: int = int(payload.get("chunk_overlap", 200))
    top_k: int = int(payload.get("top_k", 4))

    try:
        store = get_chroma_store()  # 使用默认持久化目录与集合名

        # 简化逻辑：若未入库则入库（允许重复写入不会影响检索结果，但建议生产环境做去重处理）
        try:
            text = read_online_pdf_text(url=pdf_url)
            chunks: List[str] = split_text_into_chunks(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            add_text_chunks_to_chroma(chunks, store, metadatas=[{"source_url": pdf_url}] * len(chunks))
            try:
                store.persist()
            except Exception:
                pass
        except Exception:
            # 如果读取失败，继续进行检索（假设之前已经入库）
            pass

        # 执行基于该 PDF 的相似检索（通过 metadata 过滤，仅返回该 PDF 的内容）
        docs = query_similar_texts(query=query, store=store, k=top_k, where_filter={"source_url": pdf_url})
        return [
            {"content": d.page_content, "metadata": getattr(d, "metadata", {})}
            for d in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag_search 失败: {e}")

@router.post("/embedding/rag_answer")
def rag_answer_endpoint(
    payload: dict = Body(..., example={
        "query": "what is the transformers architecture?",
        "pdf_url": "https://agent-1300436343.cos.ap-shanghai.myqcloud.com/uploads/pdf/2025/10/05/b918852f01db4bc8b7182b113adedf42.pdf",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "top_k": 4,
        "model": None,
        "temperature": 0.2
    })
):
    """检索并生成：先基于指定 PDF 执行 RAG 检索，随后将检索到的若干片段与用户问题一并交给大模型生成最终回答。"""
    query = payload.get("query")
    pdf_url = payload.get("pdf_url")
    if not query:
        raise HTTPException(status_code=400, detail="query 字段不能为空")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url 字段不能为空")

    chunk_size: int = int(payload.get("chunk_size", 1000))
    chunk_overlap: int = int(payload.get("chunk_overlap", 200))
    top_k: int = int(payload.get("top_k", 4))
    model = payload.get("model")
    temperature = float(payload.get("temperature", 0.2))

    try:
        store = get_chroma_store()  # 后端固定持久化目录与集合名

        # 若未入库则尝试入库（失败不影响检索，假设之前已入库）
        try:
            text = read_online_pdf_text(url=pdf_url)
            chunks: List[str] = split_text_into_chunks(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            add_text_chunks_to_chroma(chunks, store, metadatas=[{"source_url": pdf_url}] * len(chunks))
            try:
                store.persist()
            except Exception:
                pass
        except Exception:
            pass

        # 检索（限定为该 PDF 的内容）
        docs = query_similar_texts(query=query, store=store, k=top_k, where_filter={"source_url": pdf_url})
        contexts = [
            {"content": d.page_content, "metadata": getattr(d, "metadata", {})}
            for d in docs
        ]
        # 打印/记录检索到的片段数量与摘要
        logger.info(f"RAG检索片段数量: {len(contexts)}")
        if contexts:
            try:
                logger.debug(f"第一个片段前200字: {contexts[0]['content'][:200]}")
            except Exception:
                pass
        # 计算并记录 query 的 embedding（长度与前几个维度），失败不影响主流程
        # 已跳过 query 嵌入计算与日志
        context_text = "\n\n".join([f"[片段{i+1}]\n{c['content']}" for i, c in enumerate(contexts)])
        logger.info(f"RAG检索到的文档片段（共 {len(contexts)} 条）：\n{context_text}")
        # 组装提示并调用大模型生成最终回答
        llm = _build_llm(model=model, temperature=temperature)
        prompt = (
            "你是一位中文助手。请严格基于下方提供的文档片段回答用户问题，避免臆造；若片段中没有答案，请明确说明无法从文档中找到答案。\n\n"
            f"文档片段（共 {len(contexts)} 条）：\n{context_text}\n\n"
            f"用户问题：{query}\n\n"
            "请给出结构化、清晰且简洁的中文回答。必要时可引用片段编号进行说明。"
        )
        ai = llm.invoke(prompt)
        answer = getattr(ai, "content", str(ai))
        return {
            "answer": answer,
            "model": model or "Qwen/Qwen3-VL-235B-A22B-Instruct",
            "top_k": top_k,
            "contexts": contexts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag_answer 失败: {e}")


def _resolve_base_url(api_key: str) -> str:
    if settings.QWEN_API_BASE:
        return settings.QWEN_API_BASE
    if api_key.startswith("ms-"):
        return "https://api-inference.modelscope.cn/v1"
    return "https://dashscope.aliyuncs.com/compatible/v1"


def _build_llm(model: str | None, temperature: float = 0.2) -> ChatOpenAI:
    api_key = settings.QWEN_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Qwen API Key 未配置，请在环境变量或 .env 中设置 QWEN_API_KEY")
    base_url = _resolve_base_url(api_key)
    use_model = model or "Qwen/Qwen3-VL-235B-A22B-Instruct"
    return ChatOpenAI(api_key=api_key, base_url=base_url, model=use_model, temperature=temperature)

@router.post("/embedding/answer")
def rag_answers_endpoint(payload:dict=Body(...,example={
    "query": "what is the transformers architecture?",
    "pdf_url": "https://agent-1300436343.cos.ap-shanghai.myqcloud.com/uploads/pdf/2025/10/05/b918852f01db4bc8b7182b113adedf42.pdf",
    "model": None,
    "temperature": 0.2
})):
    # 打印 OPENAI_API_KEY（仅掩码显示，避免泄露）
    openai_key = os.getenv("OPENAI_API_KEY")
    masked = (openai_key[:6] + "..." + openai_key[-4:]) if openai_key and len(openai_key) >= 10 else ((openai_key[:6] + "...") if openai_key else "")
    logger.info(f"OPENAI_API_KEY present={bool(openai_key)}; value_masked={masked}")
    query = payload.get("query")
    pdf_url = payload.get("pdf_url")
    model = payload.get("model")
    temperature = float(payload.get("temperature", 0.2))
    if not query:
        raise HTTPException(status_code=400, detail="query 字段不能为空")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="pdf_url 字段不能为空")
    try:
        pdf_text = read_online_pdf_text(pdf_url)
        chunks: List[str] = split_text_into_chunks(pdf_text, chunk_size=1000, chunk_overlap=200)
        store =get_chroma_store()
        for chunk in chunks:
            add_text_chunks_to_chroma([chunk], store, metadatas=[{"source_url": pdf_url}])
        try:
            store.persist()
        except Exception:
            pass
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"rag_answers 失败: {e}")
