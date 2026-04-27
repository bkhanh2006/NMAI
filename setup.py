#!/usr/bin/env python3
"""
Smart Map Pro - Quick Start Guide
Hướng dẫn nhanh chạy ứng dụng
"""

import os
import subprocess
import sys

def check_python_version():
    """Kiểm tra phiên bản Python"""
    if sys.version_info < (3, 7):
        print("❌ Phiên bản Python < 3.7. Vui lòng cập nhật Python 3.7+")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True

def check_dependencies():
    """Kiểm tra và cài dependencies"""
    print("\n📦 Kiểm tra dependencies...")
    try:
        import flask
        import flask_cors
        import networkx
        import osmnx
        print("✓ Tất cả dependencies đã cài đặt")
        return True
    except ImportError:
        print("❌ Thiếu dependencies")
        print("Cài đặt bằng: pip install -r requirements.txt")
        return False

def check_graph_file():
    """Kiểm tra file đồ thị"""
    graph_path = os.path.join(os.path.dirname(__file__), 'graph', 'spd_metro.graphml')
    if os.path.exists(graph_path):
        size_mb = os.path.getsize(graph_path) / (1024 * 1024)
        print(f"✓ File đồ thị: {graph_path} ({size_mb:.1f} MB)")
        return True
    else:
        print(f"❌ Không tìm thấy: {graph_path}")
        print("💡 Tạo file bằng: python graph/graph.py")
        return False

def check_index_html():
    """Kiểm tra file giao diện"""
    index_path = os.path.join(os.path.dirname(__file__), 'index.html')
    if os.path.exists(index_path):
        print(f"✓ File giao diện: {index_path}")
        return True
    else:
        print(f"❌ Không tìm thấy: {index_path}")
        return False

def main():
    print("=" * 70)
    print("🚇 Smart Map Pro - Hướng Dẫn Nhanh")
    print("=" * 70)

    # Kiểm tra Python
    if not check_python_version():
        return

    # Kiểm tra dependencies
    if not check_dependencies():
        response = input("\nCài đặt dependencies ngay? (y/n): ")
        if response.lower() == 'y':
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

    print("\n🔍 Kiểm tra tệp...")
    # Kiểm tra file đồ thị
    if not check_graph_file():
        return

    # Kiểm tra file giao diện
    if not check_index_html():
        return

    print("\n" + "=" * 70)
    print("✅ Mọi thứ đã sẵn sàng!")
    print("=" * 70)
    print("\n🚀 Chạy server:")
    print("   python main.py")
    print("\n🌐 Mở trình duyệt:")
    print("   http://localhost:5000")
    print("\n👤 Đăng nhập Admin:")
    print("   Mật khẩu: 123456")
    print("\n" + "=" * 70)

    response = input("\nChạy server ngay? (y/n): ")
    if response.lower() == 'y':
        print("\nKhởi động server...\n")
        os.system('python main.py')

if __name__ == '__main__':
    main()
