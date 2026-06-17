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

本地本地 Git 代理 127.0.0.1:7892


LangGraph资源生成流程：
START
 -> load_profile
 -> retrieve_knowledge
 -> design_resources
 -> generate_document
 -> generate_mind_map
 -> generate_exercise
 -> generate_code_case
 -> generate_video_script
 -> safety_review
 -> save_resources
 -> END
load_profile：调用 ProfileAgent 读取学生画像。
retrieve_knowledge：调用 KnowledgeAgent 从课程知识库取知识片段，如果没有真实知识片段会报错终止。
design_resources：调用 ResourceDesignerAgent 让 DeepSeek 生成资源设计方案。
generate_document / generate_mind_map / generate_exercise / generate_code_case / generate_video_script： 这些节点根据 resource_types 判断是否生成对应资源。
safety_review：把前面生成的资源交给SafetyAgent做安全和幻觉风险审核。
save_resources：优先保存reviewed_resources，没有的话保存generated_resources，逐条写入LearningResource表。
