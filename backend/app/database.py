"""SQLite 数据库连接与会话管理。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  确保模型注册
    from .services import migrations, settings_svc
    Base.metadata.create_all(engine)
    # 旧库自动升级（幂等）：补列 / 建新表 / 默认公司 / 项目归属
    migrations.run_all(engine)
    # 初始化默认设置
    db = SessionLocal()
    try:
        settings_svc.ensure_defaults(db)
    finally:
        db.close()
