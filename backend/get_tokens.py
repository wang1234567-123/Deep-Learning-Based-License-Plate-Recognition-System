#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
获取用户JWT token的脚本
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hertz_server_django.settings')
django.setup()

from hertz_studio_django_auth.models import HertzUser
from hertz_studio_django_auth.utils.auth.token_utils import TokenUtils

def get_user_tokens():
    """获取用户token"""
    try:
        # 获取普通用户hertz
        user = HertzUser.objects.get(username='demo')
        user_roles = user.roles.all()
        print(f'找到用户: {user.username}, 角色: {[role.role_code for role in user_roles]}')
        
        # 生成token
        user_data = {
            'user_id': str(user.user_id),
            'username': user.username,
            'email': user.email,
            'roles': [role.role_code for role in user_roles],
            'permissions': []
        }
        token_data = TokenUtils.generate_token(user_data)
        print(f'普通用户token: {token_data}')
        print()
        
        # 获取管理员用户hertz
        admin_user = HertzUser.objects.get(username='hertz')
        admin_roles = admin_user.roles.all()
        print(f'找到管理员: {admin_user.username}, 角色: {[role.role_code for role in admin_roles]}')
        
        # 生成管理员token
        admin_data = {
            'user_id': str(admin_user.user_id),
            'username': admin_user.username,
            'email': admin_user.email,
            'roles': [role.role_code for role in admin_roles],
            'permissions': []
        }
        admin_token_data = TokenUtils.generate_token(admin_data)
        print(f'管理员token: {admin_token_data}')
        
        return {
            'user_token': token_data,
            'admin_token': admin_token_data
        }
        
    except Exception as e:
        print(f'错误: {e}')
        return None

if __name__ == '__main__':
    get_user_tokens()