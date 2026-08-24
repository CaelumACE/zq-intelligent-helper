"""检索日志：把每次检索的关键信息写入 JSONL，便于快速定位答非所问的原因。

- 只记录检索侧字段，不记录 LLM 完整 prompt/response
- 按天轮转，保留最近 7 天
- 仅写文件，不依赖数据库
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.logger import logger
from app.services.pg_store import pg_store

_lock = threading.Lock()
_retention_days = 7


def _log_dir() -> Path:
    return settings.DATA_DIR / 'retrieval_log'


def _log_path(ts: float | None = None) -> Path:
    dt = datetime.fromtimestamp(ts if ts is not None else time.time())
    return _log_dir() / f"retrieval_{dt.strftime('%Y-%m-%d')}.jsonl"


def _cleanup_old_logs() -> None:
    try:
        d = _log_dir()
        if not d.exists():
            return
        cutoff = time.time() - _retention_days * 86400
        for f in d.glob('retrieval_*.jsonl'):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                continue
    except Exception as exc:  # pragma: no cover - 清理失败不影响主流程
        logger.warning(f"检索日志清理失败: {exc}")


def log_retrieval(record: dict) -> None:
    """写入一条检索日志；PG 可用优先写 PG，否则写 JSONL，不阻塞问答主流程。"""
    if pg_store.insert_retrieval_log(record):
        return
    try:
        _log_dir().mkdir(parents=True, exist_ok=True)
        path = _log_path()
        line = json.dumps(record, ensure_ascii=False)
        with _lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
            _cleanup_old_logs()
    except Exception as exc:
        logger.warning(f"检索日志写入失败: {exc}")
