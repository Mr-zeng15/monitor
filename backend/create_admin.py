# -*- coding: utf-8 -*-
"""创建超级管理员（发布版首次启动使用）"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
print('=' * 50)
print('  Create superuser account')
print('=' * 50)
print()

username = input('Username (default admin): ').strip() or 'admin'
email = input('Email (optional): ').strip() or ''
password = input('Password (default admin@123): ').strip() or 'admin@123'

if User.objects.filter(username=username).exists():
    print('User {} already exists!'.format(username))
    sys.exit(1)

User.objects.create_superuser(username=username, email=email or None, password=password)
print()
print('=' * 50)
print('  Superuser {} created successfully!'.format(username))
print('  Please change the default password after login.')
print('=' * 50)
