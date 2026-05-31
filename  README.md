本地连接指令
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
# 根据requirement.txt
python -m pip install -r requirements.txt

数据库迁移指令
初始化 Alembic
alembic init alembic
自动生成迁移文件
alembic revision --autogenerate -m "描述改动"
执行所有未执行的迁移
alembic upgrade head
回滚上一个版本
alembic downgrade -1
回滚到指定版本
alembic downgrade 版本号