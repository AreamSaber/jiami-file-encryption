#!/usr/bin/env python3
"""
文件加密系统安装脚本
"""

from setuptools import setup, find_packages
import os

# 读取README文件
def read_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

# 读取requirements文件
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="file-encryption-system",
    version="1.0.0",
    author="FileEncryption Team",
    author_email="team@fileencryption.com",
    description="企业级文件加密系统，支持多层混合加密",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/fileencryption/system",
    
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security :: Cryptography",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities",
    ],
    
    python_requires=">=3.8",
    install_requires=read_requirements(),
    
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
        "gui": [
            "PyQt6>=6.6.0",
            "PySide6>=6.6.0",
        ],
        "advanced": [
            "numba>=0.58.0",
            "cython>=3.0.0",
        ],
    },
    
    entry_points={
        "console_scripts": [
            "file-encryptor=src.encryptor.main:main",
            "file-decryptor=src.decryptor.template:main",
        ],
        "gui_scripts": [
            "file-encryptor-gui=gui.encryptor_gui:main",
            "file-decryptor-gui=gui.decryptor_gui:main",
        ],
    },
    
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml", "*.txt", "*.md"],
        "gui": ["resources/*"],
        "config": ["*.json"],
    },
    
    project_urls={
        "Bug Reports": "https://github.com/fileencryption/system/issues",
        "Source": "https://github.com/fileencryption/system",
        "Documentation": "https://fileencryption.readthedocs.io/",
    },
)
