import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 加载 .env 文件中的环境变量
load_dotenv()

# 数据库连接配置
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 构建 MySQL 连接 URL
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    connect_args={
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
        "read_timeout": int(os.getenv("DB_READ_TIMEOUT_SECONDS", "10")),
        "write_timeout": int(os.getenv("DB_WRITE_TIMEOUT_SECONDS", "10")),
    },
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """FastAPI 依赖：获取数据库会话，请求结束时自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
