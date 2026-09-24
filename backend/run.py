# -*- coding: utf-8 -*-
"""
产量监控预警系统 - 纯 Python 启动器
最保险的启动方式：双击 run.py 或在命令行执行 python run.py
不依赖任何系统命令（taskkill/chcp/timeout/where）
"""
import os
import sys
import subprocess
import webbrowser
import time
import socket
from pathlib import Path

# 切换到脚本所在目录
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# 颜色输出（Windows 10+ 支持 ANSI）
if sys.platform == 'win32':
    os.system('color')

class C:
    """ANSI 颜色代码"""
    R = '\033[91m'  # 红
    G = '\033[92m'  # 绿
    Y = '\033[93m'  # 黄
    B = '\033[94m'  # 蓝
    CY = '\033[96m' # 青
    W = '\033[97m'  # 白
    E = '\033[0m'   # 结束
    BOLD = '\033[1m'


def banner():
    """打印启动横幅"""
    print(f'{C.CY}{C.BOLD}')
    print('=' * 60)
    print('   产量监控预警系统  v1.0')
    print('=' * 60)
    print(f'{C.E}')


def step(num, total, msg):
    """打印步骤"""
    print(f'{C.B}[{num}/{total}]{C.E} {msg}')


def ok(msg):
    print(f'  {C.G}[OK]{C.E} {msg}')


def warn(msg):
    print(f'  {C.Y}[WARN]{C.E} {msg}')


def err(msg):
    print(f'  {C.R}[X]{C.E} {msg}')


def info(msg):
    print(f'      {msg}')


def check_python():
    """检测 Python 版本"""
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 8):
        err(f'Python 版本过低: {v.major}.{v.minor}')
        err('需要 Python 3.8 ~ 3.12')
        return False
    ok(f'Python {v.major}.{v.minor}.{v.micro}')
    return True


def kill_old(port=8000):
    """关闭占用端口的旧进程（不依赖 taskkill）"""
    if sys.platform == 'win32':
        try:
            # 用 netstat 找占用端口的 PID
            out = subprocess.check_output(
                ['netstat', '-ano', '-p', 'TCP'],
                creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('gbk', errors='ignore')

            pids = set()
            for line in out.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            pids.add(int(parts[-1]))
                        except ValueError:
                            pass

            killed = 0
            for pid in pids:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        capture_output=True
                    )
                    killed += 1
                except Exception:
                    pass
            if killed:
                warn(f'已关闭 {killed} 个占用 {port} 端口的旧进程')
        except Exception as e:
            warn(f'清理旧进程时出错（可忽略）: {e}')


def create_venv():
    """创建虚拟环境"""
    venv_dir = ROOT / 'venv'
    if venv_dir.exists() and (venv_dir / 'Scripts' / 'python.exe').exists():
        ok('虚拟环境已存在')
        return True

    info('正在创建虚拟环境...')
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'venv', 'venv'],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        ok('虚拟环境创建成功')
        return True
    except subprocess.CalledProcessError as e:
        err(f'创建虚拟环境失败: {e}')
        return False


def get_venv_python():
    """获取 venv 里的 python.exe"""
    if sys.platform == 'win32':
        return ROOT / 'venv' / 'Scripts' / 'python.exe'
    else:
        return ROOT / 'venv' / 'bin' / 'python'


def get_active_python():
    """获取实际使用的 Python 解释器（venv 优先，没有就用系统）"""
    venv_py = get_venv_python()
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def install_deps():
    """安装依赖（使用 venv 内的 pip）"""
    venv_py = get_venv_python()
    req = ROOT / 'requirements.txt'

    info('检查并安装依赖（首次需 1-3 分钟）...')

    # 先升级 pip，避免旧版 pip 的兼容性问题
    try:
        subprocess.check_call(
            [str(venv_py), '-m', 'pip', 'install', '--upgrade', 'pip', '--disable-pip-version-check'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except Exception:
        pass  # 升级失败不影响主流程

    # 尝试多个镜像源
    mirrors = [
        None,  # 默认
        'https://pypi.tuna.tsinghua.edu.cn/simple',  # 清华
        'https://mirrors.aliyun.com/pypi/simple',    # 阿里
        'https://pypi.douban.com/simple',            # 豆瓣
        'https://mirrors.cloud.tencent.com/pypi/simple',  # 腾讯
    ]

    for mirror in mirrors:
        cmd = [str(venv_py), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(req)]
        if mirror:
            cmd += ['-i', mirror]
            src_name = mirror.split('//')[1].split('.')[0]
        else:
            src_name = '官方源'

        try:
            subprocess.check_call(
                cmd,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            ok(f'依赖安装完成（{src_name}）')
            return True
        except subprocess.CalledProcessError:
            warn(f'{src_name} 失败，尝试下一个...')
            continue

    err('所有镜像源都失败')
    info('可能是网络问题，请检查:')
    info('  1. 电脑能否访问外网')
    info('  2. 是否需要配置代理 (HTTP_PROXY 环境变量)')
    info('  3. 公司防火墙是否阻挡了 PyPI')
    return False


def migrate_db():
    """数据库迁移"""
    py = get_active_python()
    try:
        subprocess.check_call(
            [py, 'manage.py', 'migrate', '--noinput'],
            cwd=str(ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        ok('数据库就绪')
        return True
    except subprocess.CalledProcessError as e:
        err(f'数据库迁移失败: {e}')
        return False


def wait_port(port, timeout=10):
    """等待端口开始监听"""
    for i in range(timeout * 2):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False


def start_server():
    """启动 Django 服务"""
    py = get_active_python()

    print()
    print(f'{C.G}{C.BOLD}========================================{C.E}')
    print(f'{C.G}{C.BOLD}  服务已启动! 访问 http://localhost:8000/{C.E}')
    print(f'{C.G}{C.BOLD}  关闭服务: 按 Ctrl+C{C.E}')
    print(f'{C.G}{C.BOLD}========================================{C.E}')
    print()

    # 等 2 秒后打开浏览器
    def open_browser():
        time.sleep(2)
        if wait_port(8000, timeout=10):
            try:
                webbrowser.open('http://localhost:8000/')
            except Exception:
                pass
        else:
            warn('服务未在 10 秒内启动，可能正在加载...')

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 前台运行 Django
    try:
        subprocess.call(
            [py, 'manage.py', 'runserver', '0.0.0.0:8000'],
            cwd=str(ROOT)
        )
    except KeyboardInterrupt:
        print('\n服务已停止')


def main():
    banner()

    step(1, 5, '检测 Python 环境...')
    if not check_python():
        sys.exit(1)

    step(2, 5, '清理旧进程...')
    kill_old(8000)

    step(3, 5, '准备虚拟环境...')
    if not create_venv():
        sys.exit(1)

    step(4, 5, '安装依赖...')
    deps_ok = install_deps()
    if not deps_ok:
        # 降级：用系统 Python（已装好的依赖）继续
        warn('依赖安装失败，尝试用系统 Python 继续...')
        info('删除 venv 目录，强制使用系统 Python...')
        try:
            import shutil
            venv_dir = ROOT / 'venv'
            if venv_dir.exists():
                shutil.rmtree(venv_dir)
        except Exception as e:
            err(f'清理 venv 失败: {e}')

    step(5, 5, '初始化数据库...')
    if not migrate_db():
        sys.exit(1)

    start_server()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n用户取消')
    except Exception as e:
        err(f'启动失败: {e}')
        import traceback
        traceback.print_exc()
        input('按回车退出...')
