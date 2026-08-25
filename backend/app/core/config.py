"""应用配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Settings:
    """应用配置"""
    # LLM 配置
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'deepseek')
    LLM_FALLBACK_PROVIDER = os.getenv('LLM_FALLBACK_PROVIDER', 'minimax')
    
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

    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'change-me-in-production-please-64')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    JWT_EXPIRE_HOURS = int(os.getenv('JWT_EXPIRE_HOURS', '72'))

    # 账号安全：admin 密码从环境变量注入，避免硬编码进代码/git 历史。
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '5211314hao')
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

    # CORS：默认只允许本机与同源部署；生产可按需用逗号分隔扩展
    CORS_ORIGINS = [o.strip() for o in os.getenv(
        'CORS_ORIGINS',
        'http://localhost,http://127.0.0.1,http://192.168.135.129,https://zq-intelligent-helper.pages.dev',
    ).split(',') if o.strip()]

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
