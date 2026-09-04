"""搜索服务：全文检索（SQLite LIKE，ORM 参数化防注入）。"""
import json
import time

from flask import Blueprint, jsonify, request

from config import KEY_SEARCH, SEARCH_TTL, ok, redis_client
from models import Post, SessionLocal

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("")
def search():
    keyword = (request.args.get("keyword") or "").strip()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    if not keyword:
        return jsonify(ok({"posts": [], "total": 0, "page": page,
                           "has_more": False, "search_time_ms": 0}))

    cache_key = KEY_SEARCH.format(keyword, page)
    cached = redis_client.get(cache_key)
    if cached:
        return jsonify(json.loads(cached))

    t0 = time.time()
    db = SessionLocal()
    try:
        like = f"%{keyword}%"
        q = db.query(Post).filter(Post.title.like(like) | Post.content.like(like))
        total = q.count()
        posts = (q.order_by(Post.created_at.desc())
                 .offset((page - 1) * limit).limit(limit).all())
        resp = ok({
            "posts": [{"id": p.id, "title": p.title, "content": p.content[:100],
                       "category": p.category,
                       "created_at": p.created_at.isoformat() if p.created_at else None}
                      for p in posts],
            "total": total,
            "page": page,
            "has_more": page * limit < total,
            "search_time_ms": round((time.time() - t0) * 1000, 2),
        })
    finally:
        db.close()
    redis_client.set(cache_key, json.dumps(resp), ex=SEARCH_TTL)
    return jsonify(resp)
