from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "templates"
CHUNK_SUMMARIZE_PATH = BASE_DIR / "chunk_summarize.txt"
FINAL_AGGREGATE_PATH = BASE_DIR / "final_aggregate.txt"


def _read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def make_chunk_summarize_prompt(language: str = "zh") -> ChatPromptTemplate:
    """片段总结提示词：从外部模板文件加载。输入变量：paper_text"""
    system_text = _read_template(CHUNK_SUMMARIZE_PATH).replace("{{language}}", language)
    messages = [
        ("system", system_text),
        ("user", "{paper_text}"),
    ]
    return ChatPromptTemplate.from_messages(messages)


def make_final_aggregate_prompt(language: str = "zh") -> ChatPromptTemplate:
    """最终聚合提示词：从外部模板文件加载。输入变量：joined_summaries"""
    system_text = _read_template(FINAL_AGGREGATE_PATH).replace("{{language}}", language)
    messages = [
        ("system", system_text),
        ("user", "{joined_summaries}"),
    ]
    return ChatPromptTemplate.from_messages(messages)