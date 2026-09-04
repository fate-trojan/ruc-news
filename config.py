"""集中配置：数据库、Redis、JWT、爬虫、推荐超参、统一响应格式。"""
import os

import redis as redis_lib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- 数据库 ----------
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'ruc_news.db')}"

# ---------- Redis ----------
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)

# ---------- JWT ----------
SECRET_KEY = os.environ.get("SECRET_KEY", "ruc-news-dev-secret-key-change-me-in-production-2026")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24 * 7

# ---------- 爬虫 ----------
CRAWLER_BASE_URL = "https://ys.qimiaoyuanfen.com"
CRAWLER_SESSION_FILE = os.path.join(BASE_DIR, "session.json")
SESSION_COOKIE_NAME = "ys_ysxy_sess"   # 真实抓包名；文档 ys7_ysxy_session 指同一 Session
AUTH_FAIL_CODE = "7001"
CRAWLER_ENDPOINTS = {
    "latest": "/article/article/lists",
    "reply": "/article/article/lists2",
    "hot": "/article/article/datehot",
    "detail": "/article/article/info",
}
CRAWLER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; 22081212C Build/TKQ1.220829.002; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/115.0.5790.166 "
        "Mobile Safari/537.36 XWEB/5715 MMWEBSDK/20230805 MMWEBID/8447 "
        "MicroMessenger/8.0.40.2440(0x28002858) WeChat/arm64 Weixin NetType/WIFI "
        "Language/zh_CN ABI/arm64 MiniProgramEnv/android"
    ),
    "Referer": "https://servicewechat.com/wxe23b94e06f71e89a/148/page-frame.html",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}

# ---------- Redis 键名 ----------
KEY_POST_DETAIL = "post:detail:{}"
KEY_LIST_LATEST = "list:latest"
KEY_LIST_HOT = "list:hot"
KEY_MATRIX = "matrix:similarity"
KEY_NOTIF_UNREAD = "notification:unread:{}"
KEY_SEARCH = "search:res:{}:{}"

# ---------- 推荐超参 ----------
RECOMMEND_TOP_N = 10
MATRIX_TTL = 3600      # 相似度矩阵缓存 1 小时
SEARCH_TTL = 300       # 搜索缓存 5 分钟
DETAIL_TTL = 3600      # 帖子详情缓存 1 小时

# ---------- 数据保留 ----------
DATA_RETENTION_DAYS = 30

# ---------- 分区特征词（jieba 归类） ----------
CATEGORY_KEYWORDS = {
    1: ["考试", "课程", "图书馆", "论文", "绩点", "考研", "选课", "自习", "学分", "上课"],
    2: ["二手", "转让", "出售", "求购", "闲置", "价格", "九成新", "低价", "出手", "自提"],
    3: ["失物", "招领", "捡到", "丢失", "饭卡", "身份证", "学生证", "钱包", "钥匙", "寻物"],
    4: ["组队", "比赛", "活动", "招募", "一起", "队友", "报名", "参赛", "组队"],
}
CATEGORY_NAMES = {1: "综合", 2: "二手交易", 3: "失物招领", 4: "组队活动"}


def ok(data=None, message="success"):
    """统一成功响应。"""
    return {"code": 200, "data": data, "message": message}


def err(code, message):
    """统一失败响应。"""
    return {"code": code, "data": None, "message": message}
