# UPGRADE v1.0 → v1.1 — AI Agent 操作文档

> 本文档写给执行升级操作的 AI Agent，不是给人类用户的。请严格按步骤执行并在完成后按
> 「验收清单」逐项确认。所有命令均在目标 Windows 机器上以普通用户权限执行（无需管理员）。

## 0. 背景与变更范围

系统为本地 Web 应用（FastAPI + SQLite + Vue3 已构建前端），访问地址 `http://127.0.0.1:8000`。
v1.1 相对 v1.0 的变更：

**新增功能**
1. 多公司支持：新增 `companies` 表与公司管理 API（`/api/companies`），`projects` 表新增
   `company_id` 列；前端顶栏新增醒目的公司切换器，看板/列表/提醒均按公司过滤。
2. 提醒中心：新增 `GET /api/reminders`，返回三类提醒（合同续签 / 工程款结算 / 质保金到期）。
   前端每次打开页面自动弹出全屏提醒中心（有待办时），顶栏新增铃铛按钮（带角标）可随时打开。
3. 合同到期日：`contracts` 表新增 `contract_end_date` 列；未填写时续签提醒自动回退使用
   项目结束日期。
4. 系统设置新增两个参数：`renewal_remind_days`（默认30，续签提前提醒天数）、
   `settlement_remind_days`（默认7，结算提前提醒天数）。

**数据库变更（自动迁移，幂等）**
- 新建表：`companies`
- `projects` 增加列：`company_id INTEGER`（可空）
- `contracts` 增加列：`contract_end_date DATE`（可空）
- 迁移逻辑：首次启动/执行时自动创建「默认公司」，并把所有 `company_id IS NULL` 的项目
  归入它。迁移代码位于 `backend/app/services/migrations.py`，独立脚本为
  `scripts/migrate_v1_1.py`。两者幂等，重复执行无害。

**依赖变更：无**。v1.0 安装目录里的 `tools\python312` 便携环境完全复用，不需要联网、
不需要 pip install、不需要管理员权限。

## 1. 前提确认（全部满足才继续）

1. 用户已提供 v1.1 升级包（zip），内含 `项目财务系统\` 文件夹与说明文件。
2. 目标机器上已存在 v1.0 安装目录，且满足以下全部条件（记为 `<OLD>`）：
   - `<OLD>\backend\app\main.py` 存在
   - `<OLD>\tools\python312\python.exe` 存在
   - `<OLD>\backend\data\app.db` 存在（用户数据）
3. 若不知道 `<OLD>` 的位置：检查用户「启动」文件夹中
   `项目财务系统-后台服务.lnk` 的目标路径，或询问用户桌面快捷方式对应的目录。

## 2. 升级步骤（推荐：一键脚本）

1. **解压** v1.1 包到临时目录（任意位置，升级完成后可删），记 `<NEW>` =
   解压出的 `项目财务系统` 文件夹完整路径。
2. **执行一键升级**：
   ```
   cmd /c "<NEW>\upgrade.bat" "<OLD>"
   ```
   脚本自动完成：停止服务 → 备份数据库到 `<OLD>\backup_<时间戳>` → 覆盖程序文件
   （保留 `backend\data` 与 `tools\python312`）→ 执行迁移 → 重启服务 → 健康检查。
   成功标志：输出 `[OK] UPGRADE COMPLETE`。
3. 跳到第 4 节「验收清单」。

## 3. 升级步骤（备选：手动方式，一键脚本失败时使用）

```bat
:: 3.1 停止服务（无论旧服务是否在跑都执行一次）
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*app_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

:: 3.2 备份数据库
robocopy "<OLD>\backend\data" "<OLD>\backup_manual" /E

:: 3.3 覆盖程序文件（关键：排除数据目录与 Python 环境）
robocopy "<NEW>" "<OLD>" /E /XD "<NEW>tools\python312" "<NEW>backend\data" __pycache__ /XF shortcuts.txt server.log *.pyc

:: 3.4 迁移数据库（幂等；会先自动备份 app.db）
"<OLD>\tools\python312\python.exe" "<OLD>\scripts\migrate_v1_1.py"
:: 预期输出包含 RESULT: UPGRADED 或 RESULT: ALREADY_UP_TO_DATE

:: 3.5 启动服务
start "" "<OLD>\tools\python312\pythonw.exe" "<OLD>\app_server.py"
```

## 4. 验收清单（逐项执行，全部通过才算完成）

```bat
:: 4.1 健康检查（version 应为 1.1.0）
curl http://127.0.0.1:8000/api/health
:: 预期 {"ok":true,...,"version":"1.1.0"}

:: 4.2 公司 API 可用，且已有默认公司
curl http://127.0.0.1:8000/api/companies
:: 预期 items 非空，至少包含 {"name":"默认公司",...}，project_count 等于项目总数

:: 4.3 提醒中心 API 可用
curl http://127.0.0.1:8000/api/reminders
:: 预期 JSON 含 renewals/settlements/warranties/counts/total 字段

:: 4.4 旧项目已自动归属公司（company_id 不再为 null）
curl http://127.0.0.1:8000/api/projects
:: 预期每个 item 的 company_id 为非空整数，且带 company_name 字段

:: 4.5 前端为新版：浏览器打开 http://127.0.0.1:8000，
::     顶栏右侧应可见「公司切换下拉框（蓝框高亮）+ 铃铛按钮」；
::     若有到期合同/逾期节点，页面加载后会自动弹出「待办提醒中心」全屏对话框。
::     无头环境可用：
curl -s http://127.0.0.1:8000/ | findstr "assets/index"
::     并确认 assets 下 js 文件与升级前不同（文件名哈希变化）。

:: 4.6 数据完整性：升级前的项目数量与升级后一致（用 4.4 的 total 对比升级前记录）。
```

向用户报告：升级结果、验收清单各项输出、迁移摘要（added_columns / created_company /
assigned_projects）、数据库备份位置 `<OLD>\backup_<时间戳>`。

## 5. 回滚方案（仅当升级失败且服务无法启动时）

```bat
:: 停止服务（命令见 3.1）
:: 用备份恢复数据库（backup 文件夹在迁移前由 upgrade.bat / migrate_v1_1.py 自动创建）
robocopy "<OLD>\backup_<时间戳>" "<OLD>\backend\data" /E
:: 用 v1.0 安装包覆盖回程序文件（若有）；或仅删除 v1.1 新增文件后
:: 用旧版 backup 中的 app.db 覆盖 <OLD>\backend\data\app.db
:: 然后重新启动：
start "" "<OLD>\tools\python312\pythonw.exe" "<OLD>\app_server.py"
```
说明：v1.1 的数据库变更只是「加列/加表」，不修改、不删除任何 v1.0 已有列与数据，
因此旧版程序文件 + 新库通常也能运行（旧代码忽略新列），回滚风险很低。

## 6. 故障排查

| 现象 | 处理 |
|---|---|
| `upgrade.bat` 报 "does not look like an installation folder" | `<OLD>` 路径写错，重新确认 |
| 迁移脚本报 ModuleNotFoundError | 必须用 `<OLD>\tools\python312\python.exe` 执行 `<OLD>\scripts\migrate_v1_1.py`，不能跨目录混用 |
| 迁移输出 RESULT: ALREADY_UP_TO_DATE | 正常（升级过或新版启动时已自动迁移），继续验收 |
| 服务起不来 | 查看 `<OLD>\backend\data\server.log`；常见为 8000 端口被占：`netstat -ano | findstr ":8000"` 找到并关闭占用进程 |
| 4.4 仍有 company_id 为 null 的项目 | 手动执行一次 `<OLD>\tools\python312\python.exe "<OLD>\scripts\migrate_v1_1.py"` |
| 前端仍是旧界面（无公司切换器） | 强制刷新浏览器（Ctrl+F5）清除缓存；确认 `<OLD>\frontend\dist\assets` 内 js 文件名已变化 |

## 7. 全新部署（无旧版时）

若目标机器从未部署过：不需要本文档，直接按压缩包内「部署说明.txt」执行——
解压到任意目录后双击 `install_autostart.bat` 即可（新装数据库由程序自动初始化并创建默认公司）。
