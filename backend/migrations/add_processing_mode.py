"""
数据库迁移脚本：添加 processing_mode 字段

运行方法:
    python migrations/add_processing_mode.py
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.config import settings


def migrate():
    """执行迁移"""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # 检查列是否已存在
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('optimization_sessions') 
            WHERE name='processing_mode'
        """))
        
        if result.scalar() == 0:
            print("添加 processing_mode 列...")
            conn.execute(text("""
                ALTER TABLE optimization_sessions 
                ADD COLUMN processing_mode VARCHAR(50) DEFAULT 'paper_polish_enhance'
            """))
            conn.commit()
            print("✓ processing_mode 列添加成功")
        else:
            print("✓ processing_mode 列已存在，跳过迁移")
    
    print("\n数据库迁移完成!")


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"迁移失败: {e}")
        sys.exit(1)
