import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置：统一从环境变量读取"""
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "")

    # JWT 配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this-later")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # 日志配置
    LOG_DIR: str = "logs"
    LOG_FILE: str = os.path.join(LOG_DIR, "server.log")

    # 验证码配置
    SMS_CODE_EXPIRE_MINUTES: int = int(os.getenv("SMS_CODE_EXPIRE_MINUTES", "5"))

    PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
    FRONTEND_SLIDES_VENDOR_DIR: Path = Path(
        os.getenv("FRONTEND_SLIDES_VENDOR_DIR", str(PROJECT_ROOT / "app" / "third_party" / "frontend_slides"))
    )
    GENERATED_RESOURCE_DIR: Path = Path(
        os.getenv("GENERATED_RESOURCE_DIR", str(PROJECT_ROOT / "generated_resources"))
    )
    PPT_HTML_TEMPLATE_DIR: Path = Path(
        os.getenv("PPT_HTML_TEMPLATE_DIR", str(FRONTEND_SLIDES_VENDOR_DIR))
    )
    PPT_DEFAULT_SLIDE_COUNT: int = int(os.getenv("PPT_DEFAULT_SLIDE_COUNT", "8"))
    PPT_MAX_SLIDE_COUNT: int = int(os.getenv("PPT_MAX_SLIDE_COUNT", "12"))
    PPT_DEFAULT_DENSITY_MODE: str = os.getenv("PPT_DEFAULT_DENSITY_MODE", "reading_first")
    PPT_DEFAULT_STYLE: str = os.getenv("PPT_DEFAULT_STYLE", "blue-professional")
    PPT_PLAYWRIGHT_TIMEOUT_SECONDS: int = int(os.getenv("PPT_PLAYWRIGHT_TIMEOUT_SECONDS", "20"))
    PPT_SIGNED_URL_EXPIRE_SECONDS: int = int(os.getenv("PPT_SIGNED_URL_EXPIRE_SECONDS", "900"))
    PPT_GENERATE_ALL_THUMBNAILS: bool = os.getenv("PPT_GENERATE_ALL_THUMBNAILS", "false").lower() == "true"
    PPT_ALLOW_EXTERNAL_IMAGES: bool = os.getenv("PPT_ALLOW_EXTERNAL_IMAGES", "false").lower() == "true"

    VIDEO_SEARCH_ENABLED: bool = os.getenv("VIDEO_SEARCH_ENABLED", "true").lower() == "true"
    VIDEO_SEARCH_PROVIDER: str = os.getenv("VIDEO_SEARCH_PROVIDER", "bilibili")
    VIDEO_SEARCH_TIMEOUT_SECONDS: int = int(os.getenv("VIDEO_SEARCH_TIMEOUT_SECONDS", "8"))
    VIDEO_SEARCH_CACHE_TTL_SECONDS: int = int(os.getenv("VIDEO_SEARCH_CACHE_TTL_SECONDS", "43200"))
    VIDEO_SEARCH_MAX_RESULTS: int = int(os.getenv("VIDEO_SEARCH_MAX_RESULTS", "20"))
    VIDEO_SEARCH_RATE_LIMIT: float = float(os.getenv("VIDEO_SEARCH_RATE_LIMIT", "0.5"))
    VIDEO_MIN_MATCH_SCORE: float = float(os.getenv("VIDEO_MIN_MATCH_SCORE", "0.45"))
    VIDEO_MAX_RETRIES: int = int(os.getenv("VIDEO_MAX_RETRIES", "2"))

    MIND_MAP_MAX_DEPTH: int = int(os.getenv("MIND_MAP_MAX_DEPTH", "4"))
    MIND_MAP_MAX_CHILDREN: int = int(os.getenv("MIND_MAP_MAX_CHILDREN", "6"))
    MIND_MAP_MAX_INTRA_RELATIONS: int = int(os.getenv("MIND_MAP_MAX_INTRA_RELATIONS", "12"))
    MIND_MAP_MAX_CROSS_RELATIONS: int = int(os.getenv("MIND_MAP_MAX_CROSS_RELATIONS", "10"))
    MIND_MAP_MAX_RELATED_CHAPTERS: int = int(os.getenv("MIND_MAP_MAX_RELATED_CHAPTERS", "5"))
    MIND_MAP_MIN_RELATION_STRENGTH: float = float(os.getenv("MIND_MAP_MIN_RELATION_STRENGTH", "0.55"))

    RESOURCE_GENERATION_MAX_RETRIES: int = int(os.getenv("RESOURCE_GENERATION_MAX_RETRIES", "2"))
    RESOURCE_GENERATION_TASK_TIMEOUT_SECONDS: int = int(
        os.getenv("RESOURCE_GENERATION_TASK_TIMEOUT_SECONDS", "300")
    )


settings = Settings()
