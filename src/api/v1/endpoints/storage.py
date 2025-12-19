from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Optional
import uuid
import os
from datetime import datetime
import logging

from qcloud_cos import CosConfig, CosS3Client
from src.core.config import settings

router = APIRouter()


def _build_cos_client() -> CosS3Client:
    if not settings.COS_SECRET_ID or not settings.COS_SECRET_KEY or not settings.COS_REGION or not settings.COS_BUCKET:
        raise HTTPException(status_code=500, detail="COS 未配置，请检查 COS_SECRET_ID、COS_SECRET_KEY、COS_REGION、COS_BUCKET 环境变量")
    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
        Token=None,
        Scheme="https",
    )
    return CosS3Client(config)


def _build_object_key(filename: str, folder: Optional[str]) -> str:
    # 仅允许 .pdf
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext != ".pdf":
        ext = ".pdf"
    date_path = datetime.now().strftime("%Y/%m/%d")
    base_folder = folder.strip("/") if folder else "uploads/pdf"
    unique = uuid.uuid4().hex
    return f"{base_folder}/{date_path}/{unique}{ext}"


def _public_url_for(key: str) -> str:
    if settings.COS_PUBLIC_DOMAIN:
        return f"{settings.COS_PUBLIC_DOMAIN.rstrip('/')}/{key}"
    # 默认 COS 访问域名
    return f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"


@router.post("/storage/upload_pdf")
async def upload_pdf(file: UploadFile = File(...), folder: Optional[str] = None):
    # 基本校验
    if not file:
        raise HTTPException(status_code=400, detail="缺少文件参数 file")
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # 某些浏览器可能上报为 octet-stream，这里兼容；但仍强制后缀为 .pdf
        pass

    # 构建对象键
    object_key = _build_object_key(file.filename or "", folder)

    # 读取文件数据
    try:
        body = await file.read()
        if body is None or len(body) == 0:
            raise HTTPException(status_code=400, detail="文件内容为空")
        logging.info("准备上传到 COS: bucket=%s, key=%s, size=%d bytes", settings.COS_BUCKET, object_key, len(body))
    finally:
        await file.close()

    # 上传到 COS
    try:
        client = _build_cos_client()
        client.put_object(
            Bucket=settings.COS_BUCKET, Key=object_key, Body=body,
            ContentType="application/pdf"
        )
        logging.info("上传成功: key=%s", object_key)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("上传到 COS 失败: bucket=%s, key=%s, error=%s", settings.COS_BUCKET, object_key, e)
        raise HTTPException(status_code=500, detail=f"上传到 COS 失败: {e}")

    # 返回公开 URL 与对象键
    url = _public_url_for(object_key)
    return {"key": object_key, "url": url}