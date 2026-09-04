"""用户中心：登录（验证 Session 换 JWT）、行为上报。"""
import hashlib
from datetime import datetime, timedelta

import jwt
from flask import Blueprint, g, jsonify, request

from config import JWT_ALGO, JWT_EXPIRE_HOURS, SECRET_KEY, err, ok
from models import SessionLocal, User, UserAction
from utils import crawler, recommender

my_bp = Blueprint("my", __name__, url_prefix="/my")


@my_bp.route("/login", methods=["POST"])
def login():
    sess = crawler.load_session()
    if not sess:
        return jsonify(err(401, "无有效 Session")), 401
    try:
        crawler.fetch_list("latest", page=1, limit=1)  # 轻量验证
    except crawler.AuthError:
        return jsonify(err(401, "Session 已失效")), 401

    openid = hashlib.md5(sess.encode()).hexdigest()
    db = SessionLocal()
    user = db.query(User).filter(User.openid == openid).first()
    if not user:
        user = User(openid=openid, nickname=f"用户{openid[:6]}")
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()

    exp = datetime.now() + timedelta(hours=JWT_EXPIRE_HOURS)
    token = jwt.encode({"sub": str(user.id), "exp": exp}, SECRET_KEY, algorithm=JWT_ALGO)
    return jsonify(ok({"token": token, "user_id": user.id, "nickname": user.nickname}))


@my_bp.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}
    post_id = data.get("post_id")
    action_type = data.get("action_type", "click")
    if not post_id or action_type not in ("click", "view"):
        return jsonify(err(400, "post_id 或 action_type 非法")), 400

    db = SessionLocal()
    db.add(UserAction(user_id=g.user_id, post_id=post_id, action_type=action_type))
    db.commit()
    db.close()

    recommender.update_matrix()
    return jsonify(ok())
