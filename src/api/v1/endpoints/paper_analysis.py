from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import json

from src.db.session import SessionLocal
from src.models.paper import PaperAnalysis
from src.core.logger import get_logger

router = APIRouter()

@router.get("/paper/analysis/{analysis_id}")
def get_paper_analysis(analysis_id: int):
    db = SessionLocal()
    try:
        rec = db.query(PaperAnalysis).filter(PaperAnalysis.id == analysis_id).first()
        if rec is None:
            raise HTTPException(status_code=404, detail="未找到解析记录")
        raw = rec.analysis_json
        analysis = None
        if raw is not None:
            try:
                analysis = json.loads(raw)
            except Exception as e:
                logger.warning("analysis_json is non-JSON for id=%d: %s", rec.id, e)
                analysis = raw
        return {
            "id": rec.id,
            "source_url": rec.source_url,
            "is_pdf": rec.is_pdf,
            "language": rec.language,
            "chunk_count": rec.chunk_count,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
            "analysis": analysis,
        }
    finally:
        db.close()

# 列表查询接口（不分页）
@router.get("/paper/analysis")
def list_paper_analysis(
    q: Optional[str] = Query(None, description="按来源URL模糊搜索")
):
    db = SessionLocal()
    try:
        query = db.query(PaperAnalysis)
        if q:
            query = query.filter(PaperAnalysis.source_url.like(f"%{q}%"))
        items = query.order_by(PaperAnalysis.created_at.desc()).all()
        result = []
        for rec in items:
            result.append({
                "id": rec.id,
                "source_url": rec.source_url,
                "is_pdf": rec.is_pdf,
                "language": rec.language,
                "chunk_count": rec.chunk_count,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
            })
        return result
    finally:
        db.close()

# 公共方法：保存论文解析记录，返回记录ID或 None
# 供分析接口使用

# 接受 Dict 或 原始 JSON 字符串，避免二次序列化引入差异
def _save_paper_analysis(
    source_url: str,
    is_pdf: bool,
    model: Optional[str],
    language: Optional[str],
    chunk_count: int,
    base_url_used: Optional[str],
    analysis: Any,
) -> Optional[int]:
    db = SessionLocal()
    try:
        provider: Optional[str] = None
        if base_url_used:
            b = base_url_used.lower()
            if "modelscope" in b:
                provider = "modelscope"
            elif "dashscope" in b:
                provider = "dashscope"
        record = PaperAnalysis(
            source_url=source_url,
            is_pdf=is_pdf,
            model=model,
            language=language,
            chunk_count=chunk_count,
            base_url_used=base_url_used,
            analysis_json=analysis if isinstance(analysis, str) else json.dumps(analysis, ensure_ascii=False),
            provider=provider,
        )
        db.add(record)
        db.commit()
        return record.id
    except Exception as e:
        logger.error("save paper_analysis failed: %s", e)
        return None
    finally:
        db.close()