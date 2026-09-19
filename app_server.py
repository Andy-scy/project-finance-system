"""后台服务入口。

用 pythonw.exe 运行本文件即可【无任何窗口】启动系统（开机自启用）：
    pythonw.exe app_server.py
日志写入 backend/data/server.log。手动调试也可以用 python.exe 运行。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.chdir(ROOT)

LOG_PATH = os.path.join(ROOT, "backend", "data", "server.log")

# pythonw 下没有标准输出，重定向到日志文件，避免库内部打印报错
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(LOG_PATH, "a", encoding="utf-8", buffering=1)

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)
