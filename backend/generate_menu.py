#!/usr/bin/env python
"""
菜单生成器命令行工具
用于快速生成菜单配置和权限同步
"""

import os
import sys
import argparse
import django
from pathlib import Path

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hertz_server_django.settings')
django.setup()

from hertz_studio_django_utils.code_generator.menu_generator import MenuGenerator


def generate_crud_menu(args):
    """生成CRUD菜单"""
    generator = MenuGenerator()
    
    operations = args.operations.split(',') if args.operations else ['list', 'create', 'update', 'delete']
    
    menus = generator.generate_menu_config(
        module_name=args.module_name,
        model_name=args.model_name,
        operations=operations,
        parent_code=args.parent_code,
        menu_prefix=args.prefix,
        sort_order=args.sort_order,
        icon=args.icon
    )
    
    # 保存到待同步文件
    pending_file = os.path.join(project_root, 'pending_menus.py')
    with open(pending_file, 'w', encoding='utf-8') as f:
        f.write('# 待同步的菜单配置\n')
        f.write('pending_menus = [\n')
        for menu in menus:
            f.write('    {\n')
            for key, value in menu.items():
                if isinstance(value, str):
                    f.write(f"        '{key}': '{value}',\n")
                elif value is None:
                    f.write(f"        '{key}': None,\n")
                else:
                    f.write(f"        '{key}': {value},\n")
            f.write('    },\n')
        f.write(']\n')
    
    print(f"已生成 {len(menus)} 个菜单配置，保存到 pending_menus.py")
    print("请重启服务器以同步菜单到数据库")


def menu_generator_main():
    parser = argparse.ArgumentParser(description='菜单生成器')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # CRUD菜单生成命令
    crud_parser = subparsers.add_parser('crud', help='生成CRUD菜单')
    crud_parser.add_argument('module_name', help='模块名称（中文）')
    crud_parser.add_argument('model_name', help='模型名称（英文）')
    crud_parser.add_argument('--parent-code', default='system', help='父级菜单代码')
    crud_parser.add_argument('--prefix', default='system', help='菜单前缀')
    crud_parser.add_argument('--operations', help='操作列表（逗号分隔）')
    crud_parser.add_argument('--sort-order', type=int, default=1, help='排序')
    crud_parser.add_argument('--icon', help='图标')
    
    args = parser.parse_args()
    
    if args.command == 'crud':
        generate_crud_menu(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    menu_generator_main()
