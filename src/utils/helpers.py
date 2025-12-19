import base64
import hmac
import json
import time
from typing import Any, Dict, Optional
from hashlib import sha256
import requests
from io import BytesIO
from pypdf import PdfReader

from src.core.config import settings

# Base64Url 编解码（去除填充）
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding and padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _sign(message: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), message, sha256).digest()
    return _b64url_encode(sig)


def create_access_token(payload: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """生成最小可用的 HS256 JWT。
    payload 中会自动加入 iat/exp。
    """
    header = {"alg": "HS256", "typ": "JWT"}
    iat = int(time.time())
    exp_minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    exp = iat + int(exp_minutes) * 60

    data = {**payload, "iat": iat, "exp": exp}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = _sign(signing_input, settings.SECRET_KEY)
    return f"{header_b64}.{payload_b64}.{signature}"


class TokenError(Exception):
    pass


def decode_token(token: str) -> Dict[str, Any]:
    """验证并解析 HS256 JWT，返回 payload。若签名或过期验证失败，抛 TokenError。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenError("非法的令牌格式")
        header_b64, payload_b64, signature = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = _sign(signing_input, settings.SECRET_KEY)
        if not hmac.compare_digest(signature, expected_sig):
            raise TokenError("令牌签名无效")
        payload_json = _b64url_decode(payload_b64)
        payload = json.loads(payload_json.decode("utf-8"))
        # 过期校验
        now = int(time.time())
        if "exp" in payload and now > int(payload["exp"]):
            raise TokenError("令牌已过期")
        return payload
    except TokenError:
        raise
    except Exception:
        raise TokenError("令牌解析失败")



# ========= 在线 PDF 读取与解析工具 =========

def fetch_pdf_bytes(url: str, timeout: int = 30) -> bytes:
    """下载在线 PDF 并返回原始字节。
    - 若响应的 Content-Type 不是 PDF，但 URL 以 .pdf 结尾也会尝试下载。
    - 异常将以 ValueError 抛出，便于上层统一处理。
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PDFFetcher/1.0; +https://example.com)",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"无法获取 URL 内容: {e}")

    content_type = (resp.headers.get("Content-Type") or "").lower()
    is_pdf = ("application/pdf" in content_type) or url.lower().endswith(".pdf")
    if not is_pdf:
        # 不是 PDF，直接拒绝，避免误解析其他类型内容
        raise ValueError(f"目标并非 PDF 文档 (Content-Type: {content_type})")

    return resp.content


def extract_text_from_pdf_bytes(content_bytes: bytes, max_pages: int = 30) -> str:
    """从 PDF 字节中解析文本，最多处理 max_pages 页。
    - 某些页面可能无法解析文本，将被忽略。
    - 返回合并后的纯文本。
    """
    reader = PdfReader(BytesIO(content_bytes))
    n = min(len(reader.pages), max_pages)
    texts: list[str] = []
    for i in range(n):
        try:
            page = reader.pages[i]
            t = page.extract_text() or ""
            if t:
                texts.append(t)
        except Exception:
            # 无法解析的页面直接跳过
            continue
    return "\n\n".join(texts).strip()


def read_online_pdf_text(url: str, timeout: int = 30, max_pages: int = 30) -> str:
    """读取在线 PDF 并返回解析后的文本。
    组合调用 fetch_pdf_bytes 与 extract_text_from_pdf_bytes。
    """
    pdf_bytes = fetch_pdf_bytes(url, timeout=timeout)
    return extract_text_from_pdf_bytes(pdf_bytes, max_pages=max_pages)