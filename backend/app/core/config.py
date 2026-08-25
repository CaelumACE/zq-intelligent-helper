"""应用配置"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

from app.core.logger import logger

# 加载环境变量
load_dotenv()


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


class Settings:
    """应用配置"""
    # LLM 配置：S03 起默认 MiniMax，DeepSeek 作为自动回退通道。
    LLM_PROVIDER = _env("LLM_PROVIDER") or "minimax"
    LLM_FALLBACK_PROVIDER = _env("LLM_FALLBACK_PROVIDER") or "deepseek"
    
    # MiniMax 配置
    MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', '')
    MINIMAX_MODEL = os.getenv('MINIMAX_MODEL', 'MiniMax-Text-01')
    MINIMAX_BASE_URL = os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.chat/v1')
    
    # DeepSeek 配置（预留）
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
    
    # 数据库
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/gov_assistant.db')

    # JWT：不再提供硬编码默认密钥；未配置时随机生成并告警，重启后旧 token 会失效。
    JWT_SECRET = _env("JWT_SECRET") or secrets.token_hex(32)
    if not _env("JWT_SECRET"):
        logger.warning("JWT_SECRET 未配置，本次启动已随机生成，重启后所有登录态将失效，请写入 .env")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

    # 账号安全：admin 密码不再有代码默认值；未配置时随机生成并打印，仅用于首次自动 seed。
    ADMIN_PASSWORD = _env("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    if not _env("ADMIN_PASSWORD"):
        logger.warning(
            "ADMIN_PASSWORD 未配置，本次启动随机生成初始密码（请妥善保存）: %s",
            ADMIN_PASSWORD,
        )
    # demo 演示账号默认关闭；如需启用请用 DEMO_ENABLED=1 并设置 DEMO_PASSWORD。
    DEMO_ENABLED = os.getenv('DEMO_ENABLED', '0') == '1'
    DEMO_PASSWORD = os.getenv('DEMO_PASSWORD', '')
    
    # Embedding
    EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'minimax')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'embo-01')
    EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1536'))
    
    # Rerank
    RERANK_PROVIDER = os.getenv('RERANK_PROVIDER', 'offline')
    RERANK_MODEL = os.getenv('RERANK_MODEL', 'bge-reranker-base')
    RERANK_BASE_URL = os.getenv('RERANK_BASE_URL', '')
    RERANK_API_KEY = os.getenv('RERANK_API_KEY', '')

    # CORS：默认只允许本机；私有化部署在同域 nginx 反代时无需放开额外来源。
    CORS_ORIGINS = [
        o.strip()
        for o in (_env("CORS_ORIGINS") or "http://localhost,http://127.0.0.1").split(",")
        if o.strip()
    ]

    # 会话策略：True=允许同一账号多端同时在线（登录不踢旧token）；False=单点登录（后登录踢前登录）
    # 改密/被禁用/管理员重置密码始终全端失效，不受此开关影响。
    ALLOW_MULTI_SESSION = os.getenv('ALLOW_MULTI_SESSION', 'true').lower() in ('1', 'true', 'yes', 'on')

    # 速率限制：每个来源 IP 在窗口内的最大请求数
    RATE_LIMIT_MAX = int(os.getenv('RATE_LIMIT_MAX', '180'))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60'))

    # 数据目录
    DATA_DIR = Path(os.getenv('DATA_DIR', str(Path(__file__).resolve().parent.parent.parent.parent / 'data')))
    
    @property
    def llm_config(self):
        """获取当前 LLM 配置"""
        if self.LLM_PROVIDER == 'minimax':
            return {
                'api_key': self.MINIMAX_API_KEY,
                'model': self.MINIMAX_MODEL,
                'base_url': self.MINIMAX_BASE_URL,
            }
        elif self.LLM_PROVIDER == 'deepseek':
            return {
                'api_key': self.DEEPSEEK_API_KEY,
                'model': self.DEEPSEEK_MODEL,
                'base_url': self.DEEPSEEK_BASE_URL,
            }
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")

settings = Settings()
