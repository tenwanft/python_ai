from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
# 增的时候所有字段都必填，所以继承ProductBase
class ProductCreate(ProductBase):
    pass
# 更新的时候所有的都是可选的
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None

# 读取产品时，需要所有核心业务字段 + 系统生成的字段
class Product(ProductBase):
    id: int
    created_at: datetime
    update_at: datetime
    
    class Config:
        from_attributes = True  # 替代原来的 orm_mode = True
# 查询列表       
class ProductList(BaseModel):
    id: int
    name: str
    price: float
    stock: int
    
    class Config:
        from_attributes = True

# 查询参数模型
class ProductQueryParams(BaseModel):
    name: Optional[str] = None  # 用于根据名称搜索
    page_size: int = 10  # 分页大小
    page_number: int = 1  # 分页页码

# 批量操作响应
class ProductBatchResponse(BaseModel):
    message: str
    affected_count: int

# 删除响应
class ProductDeleteResponse(BaseModel):
    message: str
    id: int

# 列表响应（包含总数）
class ProductListResponse(BaseModel):
    total: int
    items: List[Product]
