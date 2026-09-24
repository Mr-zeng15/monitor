# 后端启动说明

## 环境要求
- Python 3.8.10
- Django 4.2 LTS

## 安装步骤

### 1. 创建虚拟环境（推荐）
```bash
cd backend
python -m venv venv
```

### 2. 激活虚拟环境
**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 数据库迁移
```bash
python manage.py migrate
```

### 5. 创建日志目录
```bash
mkdir logs
```

### 6. 启动开发服务器
```bash
python manage.py runserver
```

服务器将在 http://127.0.0.1:8000/ 启动

## 测试 API
访问 http://127.0.0.1:8000/api/ 应该看到：
```json
{
  "status": "success",
  "message": "产量监控预警系统API",
  "version": "1.0.0"
}
```

## 管理后台
访问 http://127.0.0.1:8000/admin/

创建超级用户：
```bash
python manage.py createsuperuser
```

## 常用命令

```bash
# 检查项目配置
python manage.py check

# 查看数据库迁移状态
python manage.py showmigrations

# 创建应用迁移文件
python manage.py makemigrations

# 执行数据库迁移
python manage.py migrate

# 启动开发服务器（指定端口）
python manage.py runserver 0.0.0.0:8000

# 收集静态文件（生产环境）
python manage.py collectstatic
```

## 目录结构
```
backend/
├── backend/              # 项目配置
│   ├── settings.py       # 主配置
│   ├── urls.py           # 主路由
│   └── wsgi.py           # WSGI配置
├── core/                 # 核心应用
│   ├── models.py         # 数据模型
│   ├── views.py          # 视图
│   ├── urls.py           # 路由
│   └── admin.py          # 管理后台
├── manage.py             # 管理命令
├── requirements.txt      # 依赖列表
└── db.sqlite3           # SQLite数据库（自动生成）
```
