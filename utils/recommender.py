"""推荐算法：jieba 分区归类 + 用户-分区协同过滤（余弦相似度）。"""
import json

import jieba
import numpy as np
import pandas as pd
from sqlalchemy import func

from config import CATEGORY_KEYWORDS, KEY_MATRIX, MATRIX_TTL, RECOMMEND_TOP_N, redis_client
from models import Post, SessionLocal, UserAction


def classify(text):
    """jieba 关键词 + 分区特征词匹配，返回分区 id (1-4)。"""
    if not text:
        return 1
    tokens = set(jieba.lcut(text))
    scores = {}
    for c, kws in CATEGORY_KEYWORDS.items():
        # 子串匹配为主（特征词多为词组），分词结果兜底
        scores[c] = sum(1 for kw in kws if kw in text) + sum(1 for kw in kws if kw in tokens)
    best = max(scores, key=scores.get)
    return best if scores[best] else 1


def index_post(post_id, title, content):
    """发帖后实时归类，返回分区 id（供 publish 复用）。"""
    cat = classify(f"{title} {content}")
    db = SessionLocal()
    db.query(Post).filter(Post.id == post_id).update({"category": cat})
    db.commit()
    db.close()
    return cat


def _cosine(m):
    """行向量余弦相似度矩阵。"""
    norm = np.linalg.norm(m, axis=1, keepdims=True)
    norm[norm == 0] = 1
    return (m / norm) @ (m / norm).T


def _user_cat_rates(db):
    """返回 {category: {user_id: rate}}，行归一化后的用户-分区点击率。"""
    rows = (
        db.query(UserAction.user_id, Post.category, func.count(UserAction.id))
        .join(Post, Post.id == UserAction.post_id)
        .group_by(UserAction.user_id, Post.category)
        .all()
    )
    df = pd.DataFrame(rows, columns=["user_id", "category", "clicks"])
    if df.empty:
        return {}
    mat = df.pivot_table(index="user_id", columns="category",
                         values="clicks", fill_value=0.0)
    rates = mat.div(mat.sum(axis=1), axis=0).fillna(0.0)
    return {int(c): rates[c].to_dict() for c in rates.columns}


def update_matrix():
    """聚合 用户-分区点击率矩阵，算余弦相似度，回写 Redis。"""
    db = SessionLocal()
    try:
        rates = _user_cat_rates(db)
    finally:
        db.close()
    if not rates:
        return
    # 用户-分区点击率矩阵（行=用户，列=分区）
    df = pd.DataFrame(rates).T.fillna(0.0)  # user_id -> {cat: rate}
    sim = _cosine(df.values)
    payload = json.dumps({"users": [int(u) for u in df.index], "matrix": sim.tolist()})
    redis_client.set(KEY_MATRIX, payload, ex=MATRIX_TTL)


def recommend(user_id, top_n=RECOMMEND_TOP_N):
    """相似用户加权预测未点击分区，返回 Top 分区的最新帖子。"""
    cached = redis_client.get(KEY_MATRIX)
    if cached is None:
        update_matrix()
        cached = redis_client.get(KEY_MATRIX)

    db = SessionLocal()
    try:
        if not cached:
            return _latest(db, top_n)
        payload = json.loads(cached)
        users = payload["users"]
        if user_id not in users:
            return _latest(db, top_n)
        cats = _predict_cats(user_id, users, np.array(payload["matrix"]), db)
        if not cats:
            return _latest(db, top_n)
        return (db.query(Post).filter(Post.category.in_(cats))
                .order_by(Post.created_at.desc()).limit(top_n).all())
    finally:
        db.close()


def _predict_cats(user_id, users, sim, db):
    """相似用户加权平均，预测目标用户对各未点击分区的分数，降序返回分区。"""
    i = users.index(user_id)
    sim_row = sim[i]
    clicked = {
        c for (c,) in db.query(Post.category)
        .join(UserAction, UserAction.post_id == Post.id)
        .filter(UserAction.user_id == user_id).distinct()
    }
    rates = _user_cat_rates(db)
    scores = {}
    for c in range(1, 5):
        if c in clicked or c not in rates:
            continue
        col = rates[c]
        num = denom = 0.0
        for j, u in enumerate(users):
            if u == user_id or u not in col:
                continue
            w = sim_row[j]
            num += w * col[u]
            denom += abs(w)
        if denom:
            scores[c] = num / denom
    return sorted(scores, key=scores.get, reverse=True)


def _latest(db, top_n):
    return db.query(Post).order_by(Post.created_at.desc()).limit(top_n).all()
