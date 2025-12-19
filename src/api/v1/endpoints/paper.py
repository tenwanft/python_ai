from fastapi import APIRouter, HTTPException,Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Iterator

import requests
from bs4 import BeautifulSoup
from io import BytesIO
from pypdf import PdfReader
import json
import re

from langchain_openai import ChatOpenAI
from src.prompts.paper_prompts import make_chunk_summarize_prompt, make_final_aggregate_prompt

from src.core.config import settings
from src.db.session import SessionLocal
from src.models.paper import PaperAnalysis
from src.api.v1.endpoints.paper_analysis import _save_paper_analysis
from src.core.logger import get_logger

router = APIRouter()


class PaperAnalyzeRequest(BaseModel):
    url: HttpUrl
    model: Optional[str] = None  # 默认选择性价比较高的模型（若未传则使用代码中的默认）
    language: Optional[str] = "zh"  # 优先返回中文解析
    temperature: Optional[float] = 0.3
    chunk_size: Optional[int] = 10000  # 文本分块大小（字符级）
    chunk_overlap: Optional[int] = 200
    max_pages_to_read: Optional[int] = 30  # PDF最多解析页数，避免过长导致成本高
    stream: Optional[bool] = False  # 是否以流式返回


def _default_qwen_base() -> str:
    # 若未配置，使用 DashScope 的 OpenAI 兼容接口地址（常用默认值）
    return settings.QWEN_API_BASE or "https://dashscope.aliyuncs.com/compatible/v1"

# 根据 API Key 前缀自动推断服务商，避免 key 与 base 不匹配导致 401
def _resolve_base_url(api_key: str) -> str:
    if settings.QWEN_API_BASE:
        return settings.QWEN_API_BASE
    # ModelScope 的 Key 通常以 ms- 开头
    if api_key.startswith("ms-"):
        return "https://api-inference.modelscope.cn/v1"
    # 其他情况默认使用 DashScope 的兼容地址
    return "https://dashscope.aliyuncs.com/compatible/v1"


def _build_llm(model: Optional[str], temperature: float = 0.3) -> ChatOpenAI:
    api_key = settings.QWEN_API_KEY
    if not api_key:
        raise HTTPException(status_code=500, detail="Qwen API Key 未配置，请在环境变量或 .env 中设置 QWEN_API_KEY")
    # 优先使用 .env 配置的 QWEN_API_BASE；否则根据 key 前缀自动选择
    base_url = _resolve_base_url(api_key)
    # 若未传模型，使用较为实惠且适合通用解析的模型
    use_model = model or "Qwen/Qwen3-VL-235B-A22B-Instruct"
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=use_model,
        temperature=temperature,
    )


def _extract_text_from_pdf(content_bytes: bytes, max_pages: int = 30) -> str:
    reader = PdfReader(BytesIO(content_bytes))
    n = min(len(reader.pages), max_pages)
    texts: List[str] = []
    for i in range(n):
        try:
            page = reader.pages[i]
            t = page.extract_text() or ""
            texts.append(t)
        except Exception:
            # 某些页面可能无法解析文本，忽略错误
            continue
    return "\n\n".join(texts).strip()


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # 清理无关标签
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    # 优先尝试抓取文章主体
    main_candidates = [
        *soup.find_all("article"),
        *soup.find_all(id=lambda x: x and "content" in x.lower()),
        *soup.find_all(class_=lambda x: x and "content" in x.lower()),
        soup.body if soup.body else soup,
    ]
    texts: List[str] = []
    for c in main_candidates:
        txt = c.get_text(separator="\n", strip=True)
        if txt:
            texts.append(txt)
    # 去重并合并
    dedup: List[str] = []
    seen = set()
    for t in texts:
        if t not in seen:
            dedup.append(t)
            seen.add(t)
    return "\n\n".join(dedup).strip()


def _fetch_and_extract(url: str, max_pages_to_read: int = 30) -> Dict[str, str]:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法获取URL内容: {e}")

    content_type = resp.headers.get("Content-Type", "").lower()
    is_pdf = ("application/pdf" in content_type) or url.lower().endswith(".pdf")

    if is_pdf:
        text = _extract_text_from_pdf(resp.content, max_pages=max_pages_to_read)
    else:
        text = _extract_text_from_html(resp.text)

    if not text:
        raise HTTPException(status_code=422, detail="从页面中未能提取到有效文本")

    return {"text": text, "is_pdf": "true" if is_pdf else "false"}


def _chunk_text(text: str, chunk_size: int = 10000, chunk_overlap: int = 200) -> List[str]:
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - chunk_overlap
        start = max(start, 0)
    return chunks


# SSE 格式化
def _sse(event: str, data: Dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _normalize_bullets(text: str) -> str:
    """
    将各种无序列表符号统一规范为 "- " 前缀；去除多余空行；合并连续空格。
    仅进行轻度格式规范，不改变语义。
    """
    if not text:
        return text
    lines = text.splitlines()
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # 常见符号替换为 "- "
        if re.match(r"^[*•·]\s+", s):
            s = re.sub(r"^[*•·]\s+", "- ", s)
        elif re.match(r"^[-–—]\s+", s):
            s = re.sub(r"^[-–—]\s+", "- ", s)
        elif re.match(r"^\d+[.)]\s+", s):
            s = re.sub(r"^\d+[.)]\s+", "- ", s)
        # 保证前缀
        if not s.startswith("- "):
            s = f"- {s}"
        # 合并多空格
        s = re.sub(r"\s+", " ", s)
        out.append(s)
    return "\n".join(out)


def _summarize_chunks(llm: ChatOpenAI, chunks: List[str], language: str = "zh") -> List[str]:
    prompt = make_chunk_summarize_prompt(language)
    chain = prompt | llm
    summaries: List[str] = []
    for c in chunks:
        try:
            res = chain.invoke({"paper_text": c})
            raw = res.content if hasattr(res, "content") else str(res)
            summaries.append(_normalize_bullets(raw))
        except Exception as e:
            summaries.append(f"[该片段总结失败: {e}]")
    return summaries


def _final_aggregate(llm: ChatOpenAI, summaries: List[str], language: str = "zh") -> Dict:
    joined = "\n\n".join(summaries)
    prompt = make_final_aggregate_prompt(language)
    chain = prompt | llm
    try:
        res = chain.invoke({"joined_summaries": joined})
        content = res.content if hasattr(res, "content") else str(res)
    except Exception as e:
        logger.error("final_aggregate invoke failed: %s", e)
        return {"error": f"final_aggregate_failed: {e}"}
    # 模型返回了什么就接收什么：若是可解析JSON则返回JSON对象，否则返回原始字符串
    try:
        data = json.loads(content)
        return data
    except Exception:
        logger.warning("final_aggregate returned non-JSON, storing raw string of length=%d", len(content) if content else 0)
        return content
    # 仅保留 summary、title，并新增 content 为模型原始输出
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return {
                "summary": data.get("summary"),
                "title": data.get("title"),
                "content": content,
            }
        else:
            return {
                "summary": None,
                "title": None,
                "content": content,
            }
    except Exception:
        return {
            "summary": None,
            "title": None,
            "content": content,
        }




# 流式分析生成器（SSE）
def _stream_paper_analysis(
    llm: ChatOpenAI,
    chunks: List[str],
    language: str,
    source_url: str,
    is_pdf: bool,
    model_name: str,
    base_url_used: str,
) -> Iterator[str]:
    summaries: List[str] = []
    total = len(chunks)
    try:
        # 开始事件
        yield _sse("start", {
            "source_url": source_url,
            "is_pdf": is_pdf,
            "chunk_count": total,
            "model": model_name,
            "base_url_used": base_url_used,
        })
        prompt = make_chunk_summarize_prompt(language)
        chain = prompt | llm
        for idx, c in enumerate(chunks):
            try:
                res = chain.invoke({"paper_text": c})
                summary = res.content if hasattr(res, "content") else str(res)
            except Exception as e:
                logger.error("chunk summarize failed at index=%d: %s", idx, e)
                summary = f"[该片段总结失败: {e}]"
            summaries.append(summary)
            # 发送事件，如果客户端断开（BrokenPipe等），停止继续发送，但仍然进行最终聚合与持久化
            try:
                yield _sse("summary", {"index": idx, "summary": summary})
                yield _sse("progress", {"current": idx + 1, "total": total})
            except Exception:
                # 客户端可能断开连接，跳出循环以便进行最终聚合和持久化
                break
        # 使用已收集的片段总结（即使不完整）进行最终聚合
        try:
            final = _final_aggregate(llm, summaries, language=language)
        except Exception as e:
            logger.error("final aggregate error: %s", e)
            final = {"summary": None, "title": None, "content": "", "error": f"final_aggregate_failed: {e}"}
        # 持久化，不依赖客户端连接状态
        try:
            _save_paper_analysis(
                source_url=source_url,
                is_pdf=is_pdf,
                model=model_name,
                language=language,
                chunk_count=len(chunks),
                base_url_used=base_url_used,
                analysis=final if isinstance(final, str) else json.dumps(final, ensure_ascii=False),
            )
        except Exception as e:
            logger.error("persist analysis failed: %s", e)
        # 尝试发送最终结果
        try:
            yield _sse("final", {"analysis": final})
        except Exception:
            pass
    except Exception as e:
        # 顶层错误处理，尽量发送错误事件
        logger.exception("stream pipeline error: %s", e)
        try:
            yield _sse("error", {"stage": "stream", "message": str(e)})
        except Exception:
            pass
    finally:
        # 始终尝试发送 end 事件
        try:
            yield _sse("end", {"message": "done"})
        except Exception:
            pass


@router.post("/paper/analyze")
def analyze_paper(req: PaperAnalyzeRequest):
    extracted = _fetch_and_extract(req.url, max_pages_to_read=req.max_pages_to_read or 30)
    text = extracted["text"]
    is_pdf = extracted["is_pdf"] == "true"

    llm = _build_llm(req.model, temperature=req.temperature or 0.3)

    # 分块
    chunks = _chunk_text(text, chunk_size=req.chunk_size or 4000, chunk_overlap=req.chunk_overlap or 200)

    # 流式返回
    if req.stream:
        model_name = req.model or "Qwen/Qwen3-VL-235B-A22B-Instruct"
        base_used = _resolve_base_url(settings.QWEN_API_KEY)
        return StreamingResponse(
            _stream_paper_analysis(
                llm, chunks, req.language or "zh", str(req.url), is_pdf, model_name, base_used
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 非流式：分段总结
    summaries = _summarize_chunks(llm, chunks, language=req.language or "zh")

    # 最终聚合为结构化JSON
    final = _final_aggregate(llm, summaries, language=req.language or "zh")

    # 持久化到数据库（使用公共方法）
    _save_paper_analysis(
        source_url=str(req.url),
        is_pdf=is_pdf,
        model=req.model or "Qwen/Qwen3-VL-235B-A22B-Instruct",
        language=req.language or "zh",
        chunk_count=len(chunks),
        base_url_used=_resolve_base_url(settings.QWEN_API_KEY),
        analysis=final if isinstance(final, str) else json.dumps(final, ensure_ascii=False),
    )

    return {
        "source_url": str(req.url),
        "is_pdf": is_pdf,
        "model": req.model or "Qwen/Qwen3-VL-235B-A22B-Instruct",
        "analysis": final,
    }