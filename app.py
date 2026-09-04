"""RUC News 入口：初始化 Flask、注册中间件与蓝图、启动 30 天清理线程。"""
import threading
import time

from flask import Flask

from config import SECRET_KEY
from middleware import auth_middleware, log_middleware
from models import init_db
from routes.info import info_bp
from routes.main import main_bp
from routes.my import my_bp
from routes.post import post_bp
from routes.search import search_bp


def _start_cleaner():
    """后台线程每天清理超过 30 天的数据（替代 APScheduler/cron）。"""
    from utils import crawler

    def _loop():
        while True:
            try:
                crawler.cleanup_old()
            except Exception as e:  # 清理失败不影响服务
                print(f"[cleanup] 失败: {e}")
            time.sleep(86400)

    threading.Thread(target=_loop, daemon=True).start()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY

    init_db()

    # 中间件（日志先注册，保证 401 请求也记录耗时）
    log_middleware(app)
    auth_middleware(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(post_bp)
    app.register_blueprint(info_bp)
    app.register_blueprint(my_bp)

    _start_cleaner()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
