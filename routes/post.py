"""发帖 & 评论 & 详情。"""
import json

from flask import Blueprint, g, jsonify, request

from config import (DETAIL_TTL, KEY_LIST_HOT, KEY_LIST_LATEST,
                    KEY_NOTIF_UNREAD, KEY_POST_DETAIL, err, ok, redis_client)
from models import Message, Post, SessionLocal
from utils import recommender

post_bp = Blueprint("post", __name__)


@post_bp.route("/publish", methods=["POST"])
def publish():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title or not content:
        return jsonify(err(400, "title 和 content 不能为空")), 400
    if len(title) > 256 or len(content) > 5000:
        return jsonify(err(400, "标题或内容长度超限")), 400

    db = SessionLocal()
    post = Post(title=title, content=content, owner_id=g.user_id)
    db.add(post)
    db.commit()
    post_id = post.id
    db.close()

    cat = recommender.index_post(post_id, title, content)
    redis_client.delete(KEY_LIST_HOT, KEY_LIST_LATEST)
    return jsonify(ok({"post_id": post_id, "category": cat}))


@post_bp.route("/post/<int:pid>")
def detail(pid):
    key = KEY_POST_DETAIL.format(pid)
    cached = redis_client.get(key)
    if cached:
        return jsonify(json.loads(cached))
    db = SessionLocal()
    try:
        post = db.get(Post, pid)
        if not post:
            return jsonify(err(404, "帖子不存在")), 404
        comments_count = (db.query(Message)
                          .filter(Message.post_id == pid, Message.type == "comment")
                          .count())
        resp = ok({
            "id": post.id, "title": post.title, "content": post.content,
            "category": post.category, "post_type": post.post_type,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "comments_count": comments_count,
        })
    finally:
        db.close()
    redis_client.set(key, json.dumps(resp), ex=DETAIL_TTL)
    return jsonify(resp)


@post_bp.route("/comment", methods=["POST"])
def comment():
    data = request.get_json(silent=True) or {}
    post_id = data.get("post_id")
    content = (data.get("content") or "").strip()
    if not post_id or not content:
        return jsonify(err(400, "post_id 和 content 不能为空")), 400

    db = SessionLocal()
    try:
        post = db.get(Post, post_id)
        if not post:
            return jsonify(err(404, "帖子不存在")), 404
        msg = Message(sender_id=g.user_id, receiver_id=post.owner_id,
                      post_id=post_id, content=content, type="comment")
        db.add(msg)
        db.commit()
        comment_id = msg.id
        author = post.owner_id
    finally:
        db.close()

    if author:
        redis_client.incr(KEY_NOTIF_UNREAD.format(author))
    return jsonify(ok({"comment_id": comment_id}))
