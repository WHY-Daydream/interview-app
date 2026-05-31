"""应用配置管理"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass


class Settings:
    # ── AI 引擎配置 ──
    # openai / claude / coze
    AI_ENGINE: str = os.getenv("AI_ENGINE", "openai")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Claude (通过 OpenAI 兼容接口)
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_BASE_URL: str = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # Coze（保留兼容）
    COZE_API_KEY: str = os.getenv("COZE_API_KEY", "")
    COZE_API_URL: str = os.getenv("COZE_API_URL", "https://api.coze.cn/v1/workflow/run")
    WORKFLOW_ID: str = os.getenv("WORKFLOW_ID", "")

    # ── 应用配置 ──
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("PORT") or os.getenv("APP_PORT", "8080"))
    APP_TITLE: str = os.getenv("APP_TITLE", "📚 每日学习笔记 → 岗位面试题生成器")
    APP_DARK_MODE: bool = os.getenv("APP_DARK_MODE", "false").lower() == "true"
    APP_LANGUAGE: str = os.getenv("APP_LANGUAGE", "zh-CN")

    # ── 数据库 ──
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'data' / 'app.db'}")

    # ── 任务超时 ──
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))

    # ── 会话存储密钥（用于 app.storage.user 持久化） ──
    STORAGE_SECRET: str = os.getenv("STORAGE_SECRET", "interview-quiz-app-secret-key-change-me")


settings = Settings()
