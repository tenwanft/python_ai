from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from src.db.base import Base

class PaperAnalysis(Base):
    __tablename__ = "paper_analysis"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(512), index=True, nullable=False)
    is_pdf = Column(Boolean, nullable=False, default=False)
    model = Column(String(255), nullable=True)
    language = Column(String(20), nullable=True)
    chunk_count = Column(Integer, nullable=True)
    provider = Column(String(50), nullable=True)
    base_url_used = Column(String(255), nullable=True)
    analysis_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())