from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(include_in_schema=False)

# Mock数据模型
class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    in_stock: bool

# Mock数据
mock_items: List[Item] = [
    Item(id=1, name="笔记本电脑", description="高性能游戏本", price=8999.99, in_stock=True),
    Item(id=2, name="机械键盘", description="青轴机械键盘", price=499.99, in_stock=True),
    Item(id=3, name="无线鼠标", description="续航长，精准定位", price=199.99, in_stock=False),
    Item(id=4, name="27寸显示器", description="4K分辨率，IPS面板", price=2499.99, in_stock=True),
    Item(id=5, name="游戏耳机", description="7.1声道，降噪麦克风", price=899.99, in_stock=True)
]

# [disabled] items route
# @router.get("/items", response_model=List[Item])
def get_items(
    skip: int = Query(0, ge=0, description="跳过前面的条目数"),
    limit: int = Query(10, ge=1, le=100, description="每页显示的条目数")
):
    """获取物品列表，支持分页"""
    return mock_items[skip : skip + limit]

# [disabled] items detail route
# @router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    """根据ID获取单个物品详情"""
    for item in mock_items:
        if item.id == item_id:
            return item
    return {"error": "Item not found"}