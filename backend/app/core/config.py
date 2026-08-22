"""应用配置"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / '.env')

class Settings:
    """应用配置"""
    # LLM 配置
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'minimax')
    LLM_FALLBACK_PROVIDER = os.getenv('LLM_FALLBACK_PROVIDER', 'deepseek')
    
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
    
    # Embedding
    EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'minimax')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'embo-01')
    EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', '1536'))
    
    # Rerank
    RERANK_PROVIDER = os.getenv('RERANK_PROVIDER', 'offline')
    RERANK_MODEL = os.getenv('RERANK_MODEL', 'bge-reranker-base')
    RERANK_BASE_URL = os.getenv('RERANK_BASE_URL', '')
    RERANK_API_KEY = os.getenv('RERANK_API_KEY', '')

    # 数据目录
    DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'data'
    
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
