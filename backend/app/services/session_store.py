"""会话存储 - 文件持久化的轻量会话管理"""
import json
import time
import uuid
from pathlib import Path
from app.core.config import settings
from app.core.logger import logger


class SessionStore:
    """会话存储服务"""

    def __init__(self, data_dir: Path = None, filename: str = "conversations.json"):
        self._data_dir = data_dir or settings.DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._data_dir / filename
        self._sessions: dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    self._sessions = json.load(f)
                logger.info(f"会话数据加载完成: {len(self._sessions)} 个会话")
            except Exception as e:
                logger.warning(f"会话数据加载失败，使用空数据: {e}")
                self._sessions = {}

    def _save(self):
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"会话数据保存失败: {e}")

    def create(self, title: str = "新对话") -> dict:
        session_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        session = {
            "id": session_id,
            "title": title,
            "messages": [],
            "createdAt": now,
            "updatedAt": now,
        }
        self._sessions[session_id] = session
        self._save()
        return dict(session)

    def get(self, session_id: str) -> dict | None:
        return dict(self._sessions.get(session_id, {})) or None

    def list(self) -> list:
        sessions = [dict(s) for s in self._sessions.values()]
        sessions.sort(key=lambda x: x.get("updatedAt", 0), reverse=True)
        return sessions

    def add_messages(self, session_id: str, messages: list) -> dict | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session["messages"].extend(messages)
        session["updatedAt"] = int(time.time() * 1000)
        if session["title"] == "新对话" and messages:
            first_user = next((m for m in messages if m.get("role") == "user"), None)
            if first_user:
                content = first_user.get("content", "")
                session["title"] = content[:20] + ("…" if len(content) > 20 else "")
        self._save()
        return dict(session)

    def get_history(self, session_id: str, limit: int = 10) -> list:
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.get("messages", [])[-limit:]

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save()
            return True
        return False


session_store = SessionStore()
