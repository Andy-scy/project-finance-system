"""路径与全局常量配置。数据全部保存在本地 backend/data 目录。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # backend/
DATA_DIR = Path(os.environ.get("PFS_DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 项目状态
PROJECT_STATUSES = ["未开始", "进行中", "已完成", "已结算", "已关闭"]
# 直接成本分类
DIRECT_CATEGORIES = ["材料", "人工", "外包", "设备", "运输", "其他直接成本"]
# 间接成本分类
INDIRECT_CATEGORIES = ["管理费用", "差旅", "办公费用", "项目管理费用", "其他间接成本"]
# 税收成本分类
TAX_CATEGORIES = ["增值税", "附加税费", "印花税", "其他税费"]
# 常用增值税/合同税率（%）
TAX_RATE_OPTIONS = [1, 1.5, 3, 5, 6, 9, 13, 20]
# 回款类型
PAYMENT_TYPES = ["合同款", "质保金", "其他"]
# 发票类型
INVOICE_TYPES = ["销项发票", "进项发票"]

PROJECT_TYPES = [
    "软件开发", "系统集成", "工程实施", "设备供应", "技术服务", "咨询设计", "其他",
]
