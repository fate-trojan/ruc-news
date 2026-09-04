"""数据抓取与 Cookie 管理：模拟小程序请求，登录失效抛 AuthError。"""
import json
import os
from datetime import datetime, timedelta

import requests

from config import (
    AUTH_FAIL_CODE, CRAWLER_BASE_URL, CRAWLER_ENDPOINTS, CRAWLER_HEADERS,
    CRAWLER_SESSION_FILE, DATA_RETENTION_DAYS, SESSION_COOKIE_NAME,
)
from models import Message, Post, SessionLocal, UserAction


class AuthError(Exception):
    """登录失效，需更新 Cookie。"""


def load_session():
    """从 session.json 读取 Session（兼容文档别名 ys7_ysxy_session）。"""
    if not os.path.exists(CRAWLER_SESSION_FILE):
        return None
    with open(CRAWLER_SESSION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(SESSION_COOKIE_NAME) or data.get("ys7_ysxy_session")


def save_session(value):
    with open(CRAWLER_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({SESSION_COOKIE_NAME: value}, f, ensure_ascii=False)


def _headers():
    h = dict(CRAWLER_HEADERS)
    sess = load_session()
    if sess:
        h["Cookie"] = f"{SESSION_COOKIE_NAME}={sess}"
    return h


def _post(path, payload):
    r = requests.post(CRAWLER_BASE_URL + path, json=payload,
                      headers=_headers(), timeout=10)
    try:
        data = r.json()
    except ValueError:
        raise AuthError(f"非 JSON 响应: {r.status_code}")
    if data.get("code") == AUTH_FAIL_CODE:
        raise AuthError(data.get("message", "请先登录"))
    return data


def fetch_list(kind="latest", page=1, limit=20):
    """抓取列表（latest / reply / hot），返回帖子 dict 列表。"""
    data = _post(CRAWLER_ENDPOINTS[kind], {"page": page, "limit": limit})
    return data.get("data", {}).get("list", []) or []


def fetch_detail(article_id):
    """抓取帖子详情。"""
    data = _post(CRAWLER_ENDPOINTS["detail"], {"id": article_id})
    return data.get("data", {})


def save_posts(raw_posts):
    """清洗 + 分区归类 + 入库（按源 id 去重），返回新入库 id 列表。"""
    from utils.recommender import classify

    db = SessionLocal()
    ids = []
    for p in raw_posts:
        sid = p.get("id")
        if not sid:
            continue
        if db.query(Post).filter(Post.source_id == sid).first():
            continue
        detail = p.get("detail") or ""
        if not detail:
            continue
        title = (p.get("title") or "").strip() or detail[:30]
        category = classify(f"{p.get('category_name') or ''} {detail}")
        db.add(Post(
            source_id=sid, title=title, content=detail, category=category,
            source_category_id=p.get("category_id"),
            source_category_name=p.get("category_name") or "",
            hot=p.get("hot") or 0,
            post_type=_type_of(category), source_url=CRAWLER_BASE_URL,
            created_at=_parse_time(p.get("create_time")),
        ))
        ids.append(sid)
    db.commit()
    db.close()
    return ids


def _parse_time(s):
    if not s:
        return datetime.now()
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.now()


def _type_of(category):
    return {2: "secondhand", 3: "lost", 4: "team"}.get(category, "normal")


def run():
    """抓取 latest + hot，入库并触发推荐矩阵更新。"""
    try:
        posts = []
        for kind in ("latest", "hot"):
            posts.extend(fetch_list(kind))
        ids = save_posts(posts)
        print(f"[crawler] 抓取完成，新增 {len(ids)} 条")
        from utils.recommender import update_matrix
        update_matrix()
        return ids
    except AuthError as e:
        print(f"[crawler] 登录失效: {e} —— 请运行 mitm_proxy 或手动更新 session.json")
        return []


def cleanup_old(days=DATA_RETENTION_DAYS):
    """删除超过 N 天的过期数据。"""
    cutoff = datetime.now() - timedelta(days=days)
    db = SessionLocal()
    for model, col in ((Post, Post.created_at),
                       (UserAction, UserAction.timestamp),
                       (Message, Message.created_at)):
        n = db.query(model).filter(col < cutoff).delete()
        print(f"[cleanup] 删除 {model.__name__} {n} 条过期记录")
    db.commit()
    db.close()
