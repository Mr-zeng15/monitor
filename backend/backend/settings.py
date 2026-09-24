"""
Django settings for backend project.
"""

from pathlib import Path
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# ★ 支持 PyInstaller frozen 模式：EXE 所在目录作为 BASE_DIR（所有运行时数据放这里）
if getattr(sys, 'frozen', False):
    # PyInstaller frozen 模式：EXE 所在目录 = 用户的工作目录
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent


import os

# ════════════════════════════════════════════════════════════
#  本地敏感配置装载（★ 2026-09-24：仓库公开化改造）
#  优先级：环境变量  >  backend/local_secrets.py  >  占位默认值
#  local_secrets.py 已加入 .gitignore，真实 Key/内网地址只留在本机。
#  新环境部署：复制 local_secrets.py.example 为 local_secrets.py 并填入真实值。
# ════════════════════════════════════════════════════════════
_SECRETS = {}
_local_secrets = BASE_DIR / 'local_secrets.py'
if _local_secrets.exists():
    _ns = {}
    with open(_local_secrets, encoding='utf-8') as _f:
        exec(compile(_f.read(), str(_local_secrets), 'exec'), _ns)
    _SECRETS = _ns.get('SECRETS', {})


def _secret(name, default=''):
    v = os.environ.get(name)
    return v if v else _SECRETS.get(name, default)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-change-this-in-production'

# SECURITY WARNING: don't run with debug turned on in production!
# ★ PyInstaller frozen 模式自动关闭 DEBUG
DEBUG = not getattr(sys, 'frozen', False)

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'


def _sqlite_options():
    """★ 2026-09-22：SQLite 连接 OPTIONS 按当前 Django 版本自适应注入。

    为什么必须自适应：runserver 启动的第一步就是 `check_migrations()` 要连库，
    连接参数一旦不被后端识别，就**不是某个接口报错、而是进程当场崩**：

        File "django/core/management/commands/runserver.py", line 136, in inner_run
            self.check_migrations()
        ...
        TypeError: Connection() got an unexpected keyword argument 'transaction_mode'

    `init_command`（PRAGMA journal_mode=WAL / synchronous=NORMAL）这个键是
    **Django 5.1** 才加入 SQLite 后端的 OPTIONS；更老的 Django 会把它原样
    透传给 `sqlite3.connect()`。requirements.txt 声明的是 `Django>=4.2`
    （本机 Anaconda 环境即 4.2.30），所以这里做版本判定而非硬写死：

      · Django >= 5.1 → 启用 WAL 初始化；
      · 更老版本      → 只保留任何版本都认的 `timeout`，并打印一行说明。
                        正式使用请走项目自带运行时
                        `backend/runtime/python/python.exe`（Django 6.1.1）。

    ★ 2026-09-22 按用户要求**移除 `transaction_mode: 'IMMEDIATE'`**
      （即 `BEGIN IMMEDIATE` 防「读→写」锁升级死锁）。这是**主动放弃**该保护：
      「并发写入 + 先读后写」的事务仍有小概率拿到 SQLITE_BUSY，且这一类
      busy_timeout 救不了。若要恢复，在下面 >= 5.1 的分支里加回一行即可：

          opts['transaction_mode'] = 'IMMEDIATE'

    ⚠ 开 WAL 后库旁会生成 db.sqlite3-wal / -shm，**备份必须走 SQLite 在线备份
      API**，不能直接 copy 主库文件（会漏掉仍在 WAL 里的事务）——实现见
      core/services/db_backup.py::_safe_copy_sqlite。
    """
    import django as _django

    opts = {'timeout': 30}   # ① 拿不到锁时等待 30s，而不是默认 5s 就抛 locked
    try:
        _maj, _min = (int(_x) for _x in _django.get_version().split('.')[:2])
    except Exception:
        _maj, _min = 0, 0
    if (_maj, _min) >= (5, 1):
        # ② WAL：读写不再互斥（写不挡读、读不挡写），页面在导入期间仍可查询；
        #    synchronous=NORMAL 在 WAL 下是安全的（断电最坏丢最后一个事务，不坏库）且更快。
        #    ★ 这里**不设** transaction_mode —— 见上方 docstring：BEGIN IMMEDIATE
        #      防死锁项已按用户要求移除。
        opts['init_command'] = 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
    # ★ 2026-09-22 按用户要求：Django < 5.1 时**静默**跳过上面的加固，不再 print 告警
    #   （runserver 的 reloader 父子进程各导入一次 settings，原本会刷两遍，看着像出故障）。
    #   注：WAL 是**库级持久属性**，即便这里跳过，库仍保持 WAL 模式；真正少的只是
    #   synchronous=NORMAL 与（已移除的）BEGIN IMMEDIATE。
    return opts


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # ★ 数据库放在 BASE_DIR（frozen 模式 = EXE 同级，正常模式 = backend 目录）
        'NAME': BASE_DIR / 'db.sqlite3',
        # ══════════════════════════════════════════════════════════════════
        # ★ 2026-09-22 并发加固（生产 = Django runserver 多线程 + 单文件 SQLite）。
        #   具体注入见上方 `_sqlite_options()`（按 Django 版本自适应，避免 <5.1 启动崩），
        #   当前保留两项：
        #     ① timeout=30        —— 拿不到锁时等待，而非默认 5s 就抛 `database is locked`；
        #     ② init_command=WAL  —— 读写不再互斥，批量导入期间页面仍可查询。
        #        ⚠ 开 WAL 后备份必须走在线备份 API，见 core/services/db_backup.py。
        #   （原「③ transaction_mode=IMMEDIATE（BEGIN IMMEDIATE 防『读→写』锁升级死锁）」
        #     已于 2026-09-22 按用户要求移除，原因与回滚方式见 `_sqlite_options()` docstring。）
        # ══════════════════════════════════════════════════════════════════
        'OPTIONS': _sqlite_options(),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# 前端打包产物目录（Django 直接托管，省去 Node.js 依赖）
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # 开发环境允许所有来源

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# 公司数据库配置（PostgreSQL）
# TODO: 部署时修改为实际的公司数据库连接信息
COMPANY_DB_CONFIG = {
    'HOST': 'localhost',        # 公司数据库服务器地址
    'PORT': 5432,               # 端口
    'NAME': 'company_db',       # 数据库名
    'USER': 'postgres',         # 用户名
    'PASSWORD': 'password',     # 密码
}

# 公司数据库表配置（根据实际表结构调整）
COMPANY_DB_TABLE = 'production_data'  # 产量数据表名
COMPANY_DB_PRODUCT_COLUMN = 'product_code'  # 产品编码列名
COMPANY_DB_DATE_COLUMN = 'production_date'  # 日期列名
COMPANY_DB_QUANTITY_COLUMN = 'quantity'     # 产量列名

# ════════════════════════════════════════════════
#  BY FAB 总览 · 公司机器人（Dify chat-messages 工作流）配置
#  也可通过环境变量覆盖：BYFAB_BOT_API_KEY / BYFAB_BOT_BASE_URL / BYFAB_BOT_USER_ID
#  TODO: 部署到公司环境时确认 Key 与地址；Key 仅存于服务端，不会下发到前端。
# ════════════════════════════════════════════════
BYFAB_BOT_API_KEY = _secret('BYFAB_BOT_API_KEY')       # ← ABL 触发机器人 API Key（占位：真实值在 local_secrets.py / 环境变量）
BYFAB_BOT_BASE_URL = _secret('BYFAB_BOT_BASE_URL', 'http://127.0.0.1/v1')  # ← 机器人 API 基址（内网地址不进仓）
BYFAB_BOT_USER_ID = 'user-001'                       # ← 调用方标识（任意唯一字符串）
# ★ 工作流必填变量（Dify chat-messages 的 inputs）。month 留 None 时自动取当前月。
BYFAB_BOT_INPUTS = {'month': None, 'week': 'W1'}

# —— DPPM 云端（2A / 2B）——
#  ★ 2026-09-23：2A 与 2B 是【两个独立的机器人应用】，各自有独立 API Key，必须分别配置。
#    旧实现两个厂共用单个 `DPPM_BOT_API_KEY`，而该值恰是 2A 的 Key →
#    2B 实际是用 2A 的机器人提问（数据来源错位），本次修正。
#  地址仍与 ABL 共用同一 Dify 网关（仅 Key 不同）；也可用同名环境变量覆盖。
#  ⚠️ 两个 Key 值必须不同，且都不能与上面的 BYFAB_BOT_API_KEY 相同。
DPPM_BOT_API_KEY_2A = _secret('DPPM_BOT_API_KEY_2A')   # ← 2A 机器人（DPPM）
DPPM_BOT_API_KEY_2B = _secret('DPPM_BOT_API_KEY_2B')   # ← 2B 机器人（抽检量）

# ════════════════════════════════════════════════
#  Excel 处理测试 · Dify workflow（上传 Excel → 跑流 → 代理下载结果）
#  与 ABL/DPPM 同一 Dify 网关；Key 仅存于服务端，不下发前端。
#  可用同名环境变量覆盖：EXCEL_FLOW_API_KEY / EXCEL_FLOW_BASE_URL
# ════════════════════════════════════════════════
import os as _os
EXCEL_FLOW_API_KEY = _secret('EXCEL_FLOW_API_KEY')
EXCEL_FLOW_BASE_URL = _secret('EXCEL_FLOW_BASE_URL', 'http://127.0.0.1/v1')
EXCEL_FLOW_USER_ID = 'user-001'          # 调用方标识（与机器人通道一致）
EXCEL_FLOW_TIMEOUT = 680                 # 单个工作流最长等待（秒），对齐 BOT_STREAM_TIMEOUT
EXCEL_FLOW_MAX_UPLOAD_MB = 20            # 上传体积上限（MB）
EXCEL_FLOW_KEEP_HOURS = 24               # 结果文件本地保留时长（小时），过期由下次任务顺带清理
