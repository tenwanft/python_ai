from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime
from src.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)  # 注意这里改为stock，并且默认值为0
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    update_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 注意字段名改为update_at，并设置onupdate


