"""Sprint 01「一件事」智能导办 API。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.routers.auth import bearer
from app.services.auth_service import decode_token
from app.services.guide_store import get_progress, roadmap_from_db, set_progress, themes_from_db
from app.services.llm_service import LLMService

router = APIRouter()


class MatchRequest(BaseModel):
    query: str


class ProgressUpdate(BaseModel):
    status: str = "done"


def current_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> int:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return int(payload.get("sub", 0))


def _theme_list():
    return [t for t in themes_from_db()]


def _match_keywords(query: str):
    query = query.strip()
    if not query:
        return []
    exact = []
    partial = []
    for theme in themes_from_db():
        kws = theme.get("keywords") or []
        if any(query == k for k in kws):
            exact.append(theme)
        elif any(k in query or query in k for k in kws):
            partial.append(theme)
    return exact or partial


@router.get("/themes")
async def list_themes():
    return {"themes": _theme_list()}


@router.post("/match")
async def match_theme(body: MatchRequest):
    hits = _match_keywords(body.query)
    if len(hits) == 1:
        theme_id = hits[0]["id"]
        roadmap = roadmap_from_db(theme_id)
        return {"matched": True, **roadmap, "total_days": roadmap["theme"]["estimated_days"]}
    if len(hits) > 1:
        return {
            "matched": False,
            "candidates": [{"id": t["id"], "name": t["name"], "score": 0.9} for t in hits],
        }
    try:
        result = await _llm_match(body.query)
    except Exception:
        result = {"matched": False, "candidates": []}
    if result.get("matched"):
        return result
    return {
        "matched": False,
        "candidates": result.get("candidates", []),
        "message": "暂未收录该事项，您可以试试“我要开饭店”“公积金贷款”等高频事项。",
    }


async def _llm_match(query: str):
    themes = _theme_list()
    theme_desc = "\n".join(
        [
            json.dumps(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "keywords": t.get("keywords", []),
                    "category": t.get("category"),
                },
                ensure_ascii=False,
            )
            for t in themes
        ]
    )
    prompt = (
        "你是政务导办匹配器。请判断用户输入与下列办事主题的匹配度，"
        "只输出 JSON，不要解释。格式：{\"id\":\"主题id\",\"score\":0.0到1.0} "
        "若无明显匹配，id 返回空字符串。\n"
        f"主题列表：\n{theme_desc}\n\n用户输入：{query}"
    )
    llm = LLMService()
    raw = await llm.chat(
        [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
        stream=False,
    )
    content = raw["choices"][0]["message"]["content"]
    data = json.loads(content.strip().strip("```json").strip("```"))
    theme_id = data.get("id", "")
    score = float(data.get("score", 0))
    if theme_id and score >= 0.8 and any(t["id"] == theme_id for t in themes):
        roadmap = roadmap_from_db(theme_id)
        return {"matched": True, **roadmap, "total_days": roadmap["theme"]["estimated_days"]}
    candidates = []
    if theme_id and 0.5 <= score < 0.8:
        theme = next((t for t in themes if t["id"] == theme_id), None)
        if theme:
            candidates.append({"id": theme["id"], "name": theme["name"], "score": score})
    return {"matched": False, "candidates": candidates}


@router.get("/theme/{theme_id}/roadmap")
async def get_roadmap(theme_id: str):
    roadmap = roadmap_from_db(theme_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="主题不存在")
    return {"total_days": roadmap["theme"]["estimated_days"], **roadmap}


@router.get("/progress/{theme_id}")
async def progress(theme_id: str, user_id: int = Depends(current_user_id)):
    return {"progress": get_progress(user_id, theme_id)}


@router.put("/progress/{theme_id}/{step_id}")
async def update_progress(
    theme_id: str,
    step_id: str,
    body: ProgressUpdate,
    user_id: int = Depends(current_user_id),
):
    result = set_progress(user_id, theme_id, step_id, body.status)
    return {"ok": True, "progress": result}
