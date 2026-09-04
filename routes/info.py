"""消息通知：列表 / 一键已读 / 未读红点。"""
from flask import Blueprint, g, jsonify, request

from config import KEY_NOTIF_UNREAD, ok, redis_client
from models import Message, SessionLocal

info_bp = Blueprint("info", __name__)


@info_bp.route("/notifications")
def notifications():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    db = SessionLocal()
    try:
        q = db.query(Message).filter(Message.receiver_id == g.user_id)
        total = q.count()
        msgs = (q.order_by(Message.created_at.desc())
                .offset((page - 1) * limit).limit(limit).all())
        unread = redis_client.get(KEY_NOTIF_UNREAD.format(g.user_id)) or "0"
        return jsonify(ok({
            "notifications": [
                {"id": m.id, "sender_id": m.sender_id, "content": m.content,
                 "type": m.type, "is_read": m.is_read,
                 "created_at": m.created_at.isoformat() if m.created_at else None}
                for m in msgs],
            "total": total,
            "page": page,
            "unread_count": int(unread),
        }))
    finally:
        db.close()


@info_bp.route("/read_all", methods=["POST"])
def read_all():
    db = SessionLocal()
    try:
        n = (db.query(Message)
             .filter(Message.receiver_id == g.user_id, Message.is_read == 0)
             .update({"is_read": 1}))
        db.commit()
    finally:
        db.close()
    redis_client.set(KEY_NOTIF_UNREAD.format(g.user_id), 0)
    return jsonify(ok({"marked_read_count": n}))
