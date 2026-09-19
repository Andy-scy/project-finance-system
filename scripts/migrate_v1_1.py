"""v1.0 -> v1.1 数据库迁移（幂等，可重复执行，失败自动回滚单步操作）。

新版服务启动时会自动执行同样迁移（backend/app/services/migrations.py），
本脚本用于升级流程中显式执行并查看结果。执行前自动备份数据库。

用法：
    <安装目录>\\tools\\python312\\python.exe <安装目录>\\scripts\\migrate_v1_1.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.database import Base, engine  # noqa: E402
from app.services.migrations import run_all  # noqa: E402


def main():
    db_path = ROOT / "backend" / "data" / "app.db"
    if db_path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = db_path.with_name(f"app.db.bak_{stamp}")
        shutil.copy2(db_path, bak)
        print(f"[1/3] database backed up -> {bak.name}")
    else:
        print("[1/3] no existing database found (fresh install), skip backup")

    Base.metadata.create_all(engine)
    print("[2/3] tables checked/created (companies etc.)")

    summary = run_all(engine)
    print(f"[3/3] migration done: added_columns={summary['added_columns']}, "
          f"created_company={summary['created_company']}, "
          f"assigned_projects={summary['assigned_projects']}")

    if summary["added_columns"]:
        print("RESULT: UPGRADED")
    else:
        print("RESULT: ALREADY_UP_TO_DATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
