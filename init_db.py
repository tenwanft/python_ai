#!/usr/bin/env python
"""数据库初始化脚本
运行此脚本可以创建数据库表结构
使用方法: python init_db.py
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import init_db

if __name__ == "__main__":
    print("开始初始化数据库...")
    init_db()
    print("数据库初始化完成！")