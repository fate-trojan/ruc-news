"""首页：推荐流、最新、悬赏、大事件、分区。"""
import json

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from config import (CATEGORY_NAMES, KEY_LIST_LATEST, RECOMMEND_TOP_N,
                    ok, redis_client)
from models import Post, SessionLocal
from utils.recommender import recommend

main_bp = Blueprint("main", __name__)


def _serialize(p):
    return {
        "id": p.id, "title": p.title, "content": p.content[:100],
        "category": p.category, "category_name": p.source_category_name,
        "post_type": p.post_type, "hot": p.hot,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _list_resp(posts, total, page, limit):
    last = posts[0].created_at if posts else None
    return ok({
        "posts": [_serialize(p) for p in posts],
        "total": total,
        "page": page,
        "has_more": page * limit < total,
        "last_post_time": last.isoformat() if last else None,
    })


def _latest_from_db(page, limit):
    db = SessionLocal()
    try:
        total = db.query(Post).count()
        posts = (db.query(Post).order_by(Post.created_at.desc())
                 .offset((page - 1) * limit).limit(limit).all())
        return posts, total
    finally:
        db.close()


@main_bp.route("/")
def home():
    user_id = getattr(g, "user_id", None)
    if user_id is None:
        posts, total = _latest_from_db(1, RECOMMEND_TOP_N)
        return jsonify(_list_resp(posts, total, 1, RECOMMEND_TOP_N))
    posts = recommend(user_id, RECOMMEND_TOP_N)
    return jsonify(_list_resp(posts, len(posts), 1, RECOMMEND_TOP_N))


@main_bp.route("/latest")
def latest():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    if page == 1:
        cached = redis_client.get(KEY_LIST_LATEST)
        if cached:
            return jsonify(json.loads(cached))
    posts, total = _latest_from_db(page, limit)
    resp = _list_resp(posts, total, page, limit)
    if page == 1:
        redis_client.set(KEY_LIST_LATEST, json.dumps(resp), ex=60)
    return jsonify(resp)


@main_bp.route("/bounty")
def bounty():
    btype = request.args.get("type", "lost")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    post_type = "team" if btype == "team" else ("secondhand" if btype == "secondhand" else "lost")
    db = SessionLocal()
    try:
        q = db.query(Post).filter(Post.post_type == post_type)
        total = q.count()
        posts = (q.order_by(Post.created_at.desc())
                 .offset((page - 1) * limit).limit(limit).all())
        return jsonify(_list_resp(posts, total, page, limit))
    finally:
        db.close()


@main_bp.route("/events")
def events():
    year = request.args.get("year")
    month = request.args.get("month")
    db = SessionLocal()
    try:
        events_list = []
        for p in db.query(Post).filter(Post.post_type == "event").order_by(Post.created_at.desc()):
            if not p.created_at:
                continue
            if year and str(p.created_at.year) != str(year):
                continue
            if month and str(p.created_at.month) != str(month):
                continue
            events_list.append({"id": p.id, "title": p.title, "detail": p.content,
                                "date": p.created_at.strftime("%Y-%m-%d")})
        return jsonify(ok({"events": events_list}))
    finally:
        db.close()


@main_bp.route("/categories")
def categories():
    db = SessionLocal()
    try:
        rows = (db.query(Post.category, func.count(Post.id)).group_by(Post.category).all())
        counts = {c: n for c, n in rows}
        cats = [{"id": c, "name": CATEGORY_NAMES[c], "count": counts.get(c, 0)}
                for c in sorted(CATEGORY_NAMES)]
        return jsonify(ok({"categories": cats}))
    finally:
        db.close()
