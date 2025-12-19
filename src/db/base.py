from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# 创建元数据对象，可以自定义命名约定
metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
})

# 创建基础模型类，所有数据库模型都将继承自这个类
Base = declarative_base(metadata=metadata)