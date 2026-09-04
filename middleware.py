"""自定义中间件：JWT 鉴权、请求日志、统一异常。"""
import time

import jwt
from flask import g, jsonify, request

from config import JWT_ALGO, SECRET_KEY

# 无需鉴权的路径（对齐接口清单中标记 ❌ 的接口）
PUBLIC_PATHS = {"/my/login", "/latest", "/bounty", "/events", "/categories", "/search"}


def _unauth(message="Token 无效或已过期"):
    return jsonify({"code": 401, "data": None, "message": message}), 401


def auth_middleware(app):
    @app.before_request
    def _auth():
        path = request.path
        if path in PUBLIC_PATHS or path.startswith("/post/") or path.startswith("/public"):
            return None
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        if not token:
            return _unauth()
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            return _unauth("Token 已过期")
        except jwt.InvalidTokenError:
            return _unauth()
        g.user_id = int(payload.get("sub"))


def log_middleware(app):
    @app.before_request
    def _start():
        g._t0 = time.time()

    @app.after_request
    def _log(resp):
        cost = (time.time() - getattr(g, "_t0", time.time())) * 1000
        print(f"{request.remote_addr} {request.method} {request.path} "
              f"{resp.status_code} {cost:.1f}ms")
        return resp
