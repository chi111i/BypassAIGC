"""
添加 processing_mode 和 emotion 模型配置字段的迁移脚本
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine
from sqlalchemy import text

def upgrade():
    """添加新字段"""
    with engine.connect() as conn:
        # 添加 processing_mode 列
        try:
            conn.execute(text("""
                ALTER TABLE optimization_sessions 
                ADD COLUMN processing_mode VARCHAR(50) DEFAULT 'paper_polish_enhance'
            """))
            conn.commit()
            print("✓ 已添加 processing_mode 列")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠ processing_mode 列已存在，跳过")
            else:
                print(f"✗ 添加 processing_mode 列失败: {e}")
        
        # 添加 emotion_model 列
        try:
            conn.execute(text("""
                ALTER TABLE optimization_sessions 
                ADD COLUMN emotion_model VARCHAR(100)
            """))
            conn.commit()
            print("✓ 已添加 emotion_model 列")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠ emotion_model 列已存在，跳过")
            else:
                print(f"✗ 添加 emotion_model 列失败: {e}")
        
        # 添加 emotion_api_key 列
        try:
            conn.execute(text("""
                ALTER TABLE optimization_sessions 
                ADD COLUMN emotion_api_key VARCHAR(255)
            """))
            conn.commit()
            print("✓ 已添加 emotion_api_key 列")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠ emotion_api_key 列已存在，跳过")
            else:
                print(f"✗ 添加 emotion_api_key 列失败: {e}")
        
        # 添加 emotion_base_url 列
        try:
            conn.execute(text("""
                ALTER TABLE optimization_sessions 
                ADD COLUMN emotion_base_url VARCHAR(255)
            """))
            conn.commit()
            print("✓ 已添加 emotion_base_url 列")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠ emotion_base_url 列已存在，跳过")
            else:
                print(f"✗ 添加 emotion_base_url 列失败: {e}")

def downgrade():
    """删除新字段（回滚）"""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE optimization_sessions DROP COLUMN processing_mode"))
            conn.execute(text("ALTER TABLE optimization_sessions DROP COLUMN emotion_model"))
            conn.execute(text("ALTER TABLE optimization_sessions DROP COLUMN emotion_api_key"))
            conn.execute(text("ALTER TABLE optimization_sessions DROP COLUMN emotion_base_url"))
            conn.commit()
            print("✓ 已删除所有新增列")
        except Exception as e:
            print(f"✗ 删除列失败: {e}")

if __name__ == "__main__":
    print("开始数据库迁移...")
    upgrade()
    print("迁移完成！")
