from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.schemas.product import Product, ProductCreate, ProductUpdate, ProductListResponse
from src.services.product_service import (
    get_product_by_id,
    get_product_by_name,
    get_products,
    create_product,
    update_product,
    delete_product,
    count_products,
    count_products_by_name,
)
from src.db.session import get_db

router = APIRouter()

@router.post("/products", response_model=Product)
def create_product_endpoint(product: ProductCreate, db: Session = Depends(get_db)):
    """创建产品"""
    db_product = create_product(db, product)
    return db_product

@router.get("/products/{product_id}", response_model=Product)
def get_product_endpoint(product_id: int, db: Session = Depends(get_db)):
    """根据ID获取产品详情"""
    db_product = get_product_by_id(db, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return db_product

@router.get("/products", response_model=ProductListResponse)
async def get_products_list(
    name: Optional[str] = Query(None, description="按产品名称搜索"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    page_number: int = Query(1, ge=1, description="页码"),
    db: Session = Depends(get_db)
):
    """
    搜索产品列表，支持按名称搜索和分页
    
    - **name**: 按产品名称模糊搜索 (可选)
    - **page_size**: 每页显示数量 (默认: 10, 最大: 100)
    - **page_number**: 页码 (默认: 1)
    """
    skip = (page_number - 1) * page_size
    
    if name:
        products = get_product_by_name(db, name)
        total = count_products_by_name(db, name)
        products = products[skip:skip + page_size]
    else:
        total = count_products(db)
        products = get_products(db, skip=skip, limit=page_size)
    
    return {"total": total, "items": products}

@router.put("/products/{product_id}", response_model=Product)
def update_product_endpoint(product_id: int, product_update: ProductUpdate, db: Session = Depends(get_db)):
    """更新产品"""
    db_product = update_product(db, product_id, product_update)
    if not db_product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return db_product

@router.delete("/products/{product_id}")
def delete_product_endpoint(product_id: int, db: Session = Depends(get_db)):
    """删除产品"""
    success = delete_product(db, product_id)
    if not success:
        raise HTTPException(status_code=404, detail="产品不存在")
    return {"message": "产品删除成功"}



