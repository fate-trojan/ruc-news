"""SQLAlchemy ORM 数据模型。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    preferences: Mapped[str] = mapped_column(Text, default="{}")  # JSON 字符串


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 源站帖子 id
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[int] = mapped_column(Integer, default=1)             # 业务分区 1-4（特征词归类）
    source_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 源站真实 category_id
    source_category_name: Mapped[str] = mapped_column(String(64), default="")       # 源站真实版块名
    hot: Mapped[int] = mapped_column(Integer, default=0)                  # 热度
    post_type: Mapped[str] = mapped_column(String(16), default="normal")  # normal/lost/secondhand/team/event
    source_url: Mapped[str] = mapped_column(String(512), default="")
    owner_id: Mapped[int] = mapped_column(Integer, default=0)             # 0 = 抓取帖
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class UserAction(Base):
    __tablename__ = "user_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    post_id: Mapped[int] = mapped_column(Integer, index=True)
    action_type: Mapped[str] = mapped_column(String(16), default="click")  # click/view
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(Integer, default=0)
    receiver_id: Mapped[int] = mapped_column(Integer, index=True)
    post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 评论关联的帖子
    content: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(16), default="system")        # comment/system
    is_read: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
