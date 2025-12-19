from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.models.product import Product
from src.schemas.product import ProductCreate, ProductUpdate
from typing import Optional

# 创建
def create_product(db: Session, product: ProductCreate) -> Product:
    try:
        db_product = Product(
            name=product.name,
            description=product.description,
            price=product.price,
            stock=product.stock,
        )
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product
    except SQLAlchemyError as e:
        db.rollback()
        raise e

# 查询（分页）
def get_products(db: Session, skip: int = 0, limit: int = 100) -> list[Product]:
    return db.query(Product).offset(skip).limit(limit).all()

# 按名称查询（支持精确匹配）
def get_product_by_name(db: Session, product_name: str) -> list[Product]:
    return db.query(Product).filter(Product.name == product_name).all()

# 查询（按ID）
def get_product_by_id(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id).first()

# 统计数量（全部）
def count_products(db: Session) -> int:
    return db.query(Product).count()

# 统计数量（按名称）
def count_products_by_name(db: Session, product_name: str) -> int:
    return db.query(Product).filter(Product.name == product_name).count()

# 更新
def update_product(db: Session, product_id: int, product_update: ProductUpdate) -> Optional[Product]:
    try:
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            return None
        update_data = product_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_product, field, value)
        db.commit()
        db.refresh(db_product)
        return db_product
    except SQLAlchemyError as e:
        db.rollback()
        raise e

# 删除
def delete_product(db: Session, product_id: int) -> bool:
    try:
        db_product = db.query(Product).filter(Product.id == product_id).first()
        if not db_product:
            return False
        db.delete(db_product)
        db.commit()
        return True
    except SQLAlchemyError as e:
        db.rollback()
        raise e