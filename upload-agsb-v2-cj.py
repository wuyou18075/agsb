#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import random
import time
import shutil
import re
import base64
import socket
import subprocess
import platform
from datetime import datetime
import uuid
from pathlib import Path
import urllib.request
import ssl
import tempfile
import argparse

# 全局变量
INSTALL_DIR = Path.home() / ".agsb"  # 用户主目录下的隐藏文件夹，避免root权限
CONFIG_FILE = INSTALL_DIR / "config.json"
SB_PID_FILE = INSTALL_DIR / "sbpid.log"
ARGO_PID_FILE = INSTALL_DIR / "sbargopid.log"
LIST_FILE = INSTALL_DIR / "list.txt"
LOG_FILE = INSTALL_DIR / "argo.log"
DEBUG_LOG = INSTALL_DIR / "python_debug.log"
CUSTOM_DOMAIN_FILE = INSTALL_DIR / "custom_domain.txt"  # 存储最终使用的域名

# ====== 全局可配置参数（可通过环境变量覆盖） ======
USER_NAME = os.getenv("USER_NAME", "521")  # 用户名，默认值为 "521"
UUID = os.getenv("UUID", "")  # UUID，默认值为空，自动生成
PORT = int(os.getenv("PORT", "0"))  # Vmess端口，默认值为 0（自动生成）
DOMAIN = os.getenv("DOMAIN", "")  # 域名，默认值为空（自动获取）
CF_TOKEN = os.getenv("TOKEN", "")  # Cloudflare Token，默认值为空（使用 Quick Tunnel）
# =========================================

# 添加命令行参数解析
def parse_args():
    parser = argparse.ArgumentParser(description="ArgoSB Python3 一键脚本 (支持自定义域名和Argo Token)")
    parser.add_argument("action", nargs="?", default="install",
                        choices=["install", "status", "update", "del", "uninstall", "cat"],
                        help="操作类型: install(安装), status(状态), update(更新), del(卸载), cat(查看节点)")
    parser.add_argument("--domain", "-d", dest="agn", help="设置自定义域名 (例如: xxx.trycloudflare.com 或 your.custom.domain)")
    parser.add_argument("--uuid", "-u", help="设置自定义UUID")
    parser.add_argument("--port", "-p", dest="vmpt", type=int, help="设置自定义Vmess端口")
    parser.add_argument("--agk", "--token", dest="agk", help="设置 Argo Tunnel Token (用于Cloudflare Zero Trust命名隧道)")
    parser.add_argument("--user", "-U", dest="user", help="设置用户名（用于上传文件名）")

    return parser.parse_args()

# 网络请求函数
def http_get(url, timeout=10):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"HTTP请求失败: {url}, 错误: {e}")
        write_debug_log(f"HTTP GET Error: {url}, {e}")
        return None

def download_file(url, target_path, mode='wb'):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as response, open(target_path, mode) as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"下载文件失败: {url}, 错误: {e}")
        write_debug_log(f"Download Error: {url}, {e}")
        return False

# 脚本信息
def print_info():
    print("\033[36m╭───────────────────────────────────────────────────────────────╮\033[0m")
    print("\033[36m│             \033[33m✨ ArgoSB Python3 自定义域名版 ✨              \033[36m│\033[0m")
    print("\033[36m├───────────────────────────────────────────────────────────────┤\033[0m")
    print("\033[36m│ \033[32m版本: 25.7.0 (支持Argo Token及交互式输入)                 \033[36m│\033[0m")
    print("\033[36m╰───────────────────────────────────────────────────────────────╯\033[0m")

# 打印使用帮助信息
def print_usage():
    print("\033[33m使用方法:\033[0m")
    print("  \033[36mpython3 script.py\033[0m                     - 交互式安装或启动服务")
    print("  \033[36mpython3 script.py install\033[0m             - 安装服务 (可配合参数)")
    print("  \033[36mpython3 script.py --agn example.com\033[0m   - 使用自定义域名安装")
    print("  \033[36mpython3 script.py --uuid YOUR_UUID\033[0m      - 使用自定义UUID安装")
    print("  \033[36mpython3 script.py --vmpt 12345\033[0m         - 使用自定义端口安装")
    print("  \033[36mpython3 script.py --agk YOUR_TOKEN\033[0m     - 使用Argo Tunnel Token安装")
    print("  \033[36mpython3 script.py status\033[0m              - 查看服务状态和节点信息")
    print("  \033[36mpython3 script.py cat\033[0m                 - 查看单行节点列表")
    print("  \033[36mpython3 script.py update\033[0m              - 更新脚本")
    print("  \033[36mpython3 script.py del\033[0m                 - 卸载服务")
    print()
    print("\033[33m支持的环境变量:\033[0m")
    print("  \033[36mexport USER_NAME=myusername\033[0m           - 设置自定义用户名")
    print("  \033[36mexport UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\033[0m - 设置自定义UUID")
    print("  \033[36mexport PORT=12345\033[0m                      - 设置自定义Vmess端口")
    print("  \033[36mexport DOMAIN=your-domain.com\033[0m          - 设置自定义域名")
    print("  \033[36mexport TOKEN=YOUR_ARGO_TUNNEL_TOKEN\033[0m    - 设置Argo Tunnel Token")
    print()

# 写入日志函数
def write_debug_log(message):
    try:
        if not INSTALL_DIR.exists():
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"写入日志失败: {e}")

# 省略其余代码（与原始脚本相同）
