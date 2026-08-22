"""日志配置"""
import logging
import sys

# 创建 logger
logger = logging.getLogger("gov_assistant")
logger.setLevel(logging.INFO)

# 控制台输出
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
