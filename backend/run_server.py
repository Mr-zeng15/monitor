# -*- coding: utf-8 -*-
"""
产量监控预警系统 - 启动入口（★ 已不在当前部署链路上，见下）
================================
☠ 现状（2026-09-23 核实）：
  当前部署入口是 `start.bat` → `runtime\\python\\python.exe manage.py runserver`。
  本文件原先设的是旧目录结构的 `core.settings`（settings 早已搬到
  `backend\\backend\\settings.py`）→ 直接 `python run_server.py` 会立刻
  ModuleNotFoundError，**跑不起来**。（下面第 54 行已顺手修正为 backend.settings。）
  ★ 保留策略（备份/快照/日志 + 过期业务行）的**权威自动清理在 `manage.py`
    的 `_maybe_retention()`**（仅 runserver 触发）；本文件保留同名逻辑只为
    兼容旧 EXE 打包路径（见 `产量监控系统.spec`）。

同时兼容两种运行模式：
1. 开发模式：python run_server.py
2. PyInstaller 打包模式：产量监控系统.exe

PyInstaller 关键点：
- sys._MEIPASS 指向临时解压目录（包含 Python 标准库、第三方包、隐藏导入的 data）
- 真实业务文件（数据库、media、上传）必须放在 EXE 同级目录
- 静态文件（前端 dist）放在 EXE 同级的 static/frontend/，让 Django serve
"""
import os
import sys
import socket
from pathlib import Path


# ==================== 路径处理 ====================
# 是否在 PyInstaller frozen 包里运行？
FROZEN = getattr(sys, 'frozen', False)
MEIPASS = getattr(sys, '_MEIPASS', None)

# EXE 所在目录（所有运行时数据：db、上传、配置 都放这里）
if FROZEN:
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    EXE_DIR = Path(__file__).resolve().parent

# 切到 EXE 目录（确保 manage.py 同级能找到）
os.chdir(EXE_DIR)
# 关键：把 EXE_DIR 加进 sys.path，让 settings / core 可被 import
if str(EXE_DIR) not in sys.path:
    sys.path.insert(0, str(EXE_DIR))

# PyInstaller 时，_MEIPASS 里才有真正的代码；正常运行时 EXE_DIR 就有
SRC_DIR = Path(MEIPASS) if FROZEN else EXE_DIR

# ==================== 引导横幅 ====================
BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║          产量监控预警系统  /  Production Monitor         ║
║          Yield Monitoring & Early Warning System         ║
║                                                          ║
║  启动模式: {mode:^10s}                                     ║
║  数据库:   {db:^10s}                                      ║
║  端口:     {port:^10d}                                    ║
╚══════════════════════════════════════════════════════════╝
""".strip()


# ==================== Django 引导 ====================
os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.settings'  # 2026-09-23 修正：settings 已从 core/ 搬到 backend/backend/

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402


# ==================== 工具函数 ====================
def is_port_in_use(port: int) -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(('127.0.0.1', port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def open_browser(url: str, delay: float = 1.5) -> None:
    """延迟 N 秒后调系统默认浏览器打开 URL"""
    import threading
    import time
    import webbrowser

    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


# ==================== 主流程 ====================
def main() -> int:
    port = int(os.environ.get('PORT', '8000'))

    # 0. 打印横幅
    print(BANNER.format(
        mode='PyInstaller' if FROZEN else '开发模式',
        db=str(Path(getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME', '?'))),
        port=port,
    ))

    # 1. 检查端口
    if is_port_in_use(port):
        print(f'\n[!] 端口 {port} 已被占用！')
        print(f'    解决方法：')
        print(f'      1. 关闭占用该端口的程序')
        print(f'      2. 或设置环境变量 PORT=另一个端口 再启动')
        print(f'         例如：set PORT=8765 && 启动.bat\n')
        try:
            input('按回车键退出...')
        except EOFError:
            pass
        return 1

    # 2. 首次启动：自动 migrate
    db_path = Path(getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME', ''))
    # ★ 种子库兜底（防升级覆盖丢数据）：无 db.sqlite3 时从 db.sqlite3.seed 生成；
    #   已有 db.sqlite3（老版本数据）直接使用，绝不覆盖 → 升级数据 100% 保留
    if db_path and not db_path.exists():
        seed_path = Path(str(db_path) + '.seed')
        if seed_path.exists():
            import shutil
            shutil.copy2(str(seed_path), str(db_path))
            print(f'[初始化] 已从种子库生成数据库（{seed_path.name} → {db_path.name}）')
    is_first_run = (not db_path.exists()) if db_path else False

    if is_first_run:
        print('[初始化] 首次启动，正在创建数据库...')

    # ★ 数据持久化：每次启动先自动备份数据库（保留最近 10 份，误操作可回滚）
    try:
        from core.services.db_backup import backup_db
        _bak = backup_db(db_path=str(db_path) if db_path else None)
        if _bak:
            print('[持久化] 已自动备份数据库 → ' + Path(_bak).name)
    except Exception as e:
        print('[持久化] 自动备份失败（不影响启动）: ' + str(e))

    # ★ 2026-09-23 保留策略：启动时收口，防止 db.sqlite3 与周边目录越积越多。
    #     · 技术文件：backups/ ≤10 份且 ≤30 天、data_snapshots/ ≤20 份且 ≤90 天、logs/ ≤90 天
    #   ★ 下面这段与 `manage.py::_maybe_retention()` 是**同一套动作的两处落点**：
    #     当前部署真正走的是 start.bat → manage.py runserver（那里的才是权威实现）；
    #     本文件历史上是入口，故保留同样逻辑，避免旧 EXE 打包路径漏掉清理。
    #   ★ 原则不变：绝不能挂 AppConfig.ready()（任何 django.setup() 都会触发，
    #     `python -c` 场景下曾因此误删真实日志）。
    #   ★ 不含 VACUUM（需独占锁 + 耗时，会拖慢启动）→ 手动 `python backup_db.py prune --vacuum`
    try:
        from core.services.db_backup import prune_all
        _res = prune_all(db_path=str(db_path) if db_path else None, dry_run=False)
        _n = sum(len(v[0]) for v in _res.values() if isinstance(v, tuple))
        if _n:
            print('[保留策略] 已清理 ' + str(_n) + ' 个过期文件（备份 / 快照 / 日志）')
    except Exception as e:
        print('[保留策略] 文件清理失败（不影响启动）: ' + str(e))

    print('[1/3] 正在执行数据库迁移...')
    try:
        call_command('migrate', '--noinput', verbosity=0)
        print('      ✓ 数据库迁移完成')
    except Exception as e:
        print(f'      ✗ 数据库迁移失败：{e}')
        try:
            input('按回车键退出...')
        except EOFError:
            pass
        return 1

    # ★ 业务数据保留策略（★ 会真的删行，不可逆）：preplan_row 是**预排筛选 与
    #   审核决议中心共用的同一张表**（exported 只是"已导出"标记），所以「清预排」和
    #   「清决议」是同一个动作。默认保留最近 6 个月，超期全清、只留 plan_ym=0（未归类）。
    #   ★ 必须放在 migrate 之后：老版本库里可能还没有 plan_ym 列，先迁移再查表。
    #   ★ 每次删除都往 logs/destructive_YYYYMMDD.log 留审计；失败只警告、绝不阻断启动。
    #     想保留决策痕迹（决议/存档/longlife 永不被清）→ 见 core/services/retention.PROTECT_DECIDED
    try:
        from core.services.retention import prune_business_rows
        _biz = prune_business_rows(dry_run=False)
        if _biz.get('deleted'):
            print('[保留策略] 已清理 ' + str(_biz['deleted']) + ' 行过期业务数据'
                  '（预排 / 决议，保留最近 ' + str(_biz['months']) + ' 个月）')
    except Exception as e:
        print('[保留策略] 业务数据清理失败（不影响启动）: ' + str(e))

    # 3. 收集静态文件（生产环境）
    if not getattr(settings, 'DEBUG', False):
        print('[2/3] 正在收集静态文件...')
        try:
            call_command('collectstatic', '--noinput', verbosity=0)
            print('      ✓ 静态文件收集完成')
        except Exception as e:
            print(f'      [!] 静态文件收集跳过：{e}')

    # 4. 启动服务
    print('[3/3] 正在启动 Web 服务...')
    print()
    print('=' * 60)
    print(f'  ✅  服务已启动:  http://127.0.0.1:{port}/')
    print(f'  📂  数据库位置:  {db_path}')
    print(f'  📁  EXE 目录:    {EXE_DIR}')
    print(f'  ⏹   停止服务:  按 Ctrl+C 或关闭本窗口')
    print('=' * 60)
    print()

    # 自动打开浏览器（仅首次或显式设置）
    auto_open = os.environ.get('NO_BROWSER', '').lower() not in ('1', 'true', 'yes')
    if auto_open and not is_first_run or os.environ.get('FORCE_BROWSER'):
        open_browser(f'http://127.0.0.1:{port}/')

    # 5. 启动 Django dev server
    from django.core.management import execute_from_command_line
    try:
        execute_from_command_line(['manage.py', 'runserver', f'0.0.0.0:{port}', '--noreload', '--insecure'])
    except KeyboardInterrupt:
        print('\n[已停止] 服务已关闭')
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
