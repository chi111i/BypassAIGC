"""测试数据库初始化"""
from app.database import Base, engine, init_db
from sqlalchemy import inspect

print("开始初始化数据库...")
init_db()

print("\n检查所有表:")
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"找到 {len(tables)} 个表:")
for table in sorted(tables):
    columns = inspector.get_columns(table)
    print(f"\n  ✓ {table} ({len(columns)} 列)")
    for col in columns[:5]:  # 只显示前5列
        print(f"    - {col['name']}: {col['type']}")
    if len(columns) > 5:
        print(f"    ... 还有 {len(columns) - 5} 列")

print("\n数据库初始化完成!")
