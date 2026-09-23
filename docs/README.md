# 文件加密系统 v1.0.0

🔐 **企业级数据保护解决方案**

一个功能强大、安全可靠的文件加密系统，支持多种加密算法、图形界面和命令行操作。

## ✨ 主要特性

### 🔒 强大的加密功能
- **多种加密算法**: AES-256、ChaCha20、RSA、Salsa20、Blowfish、Twofish
- **多层加密**: 支持分层和并行加密模式
- **自定义算法**: 位混洗、旋转密码、替换密码等
- **隐写术**: 支持图像和文本隐写

### 🖥️ 用户友好的界面
- **图形界面**: 基于PyQt6/PySide6的现代GUI
- **命令行界面**: 功能完整的CLI工具
- **批处理**: 支持批量文件处理
- **进度显示**: 实时进度跟踪和显示

### ⚡ 高性能优化
- **大文件支持**: 优化的大文件处理
- **多线程处理**: 并行加密提升性能
- **内存管理**: 智能内存使用和监控
- **流式处理**: 支持流式文件处理

### 🛡️ 安全保护
- **双程序分离**: 加密器和解密器完全独立
- **反调试保护**: 防止逆向工程
- **反虚拟机检测**: 检测虚拟环境
- **代码混淆**: 保护程序逻辑

## 🚀 快速开始

### 安装依赖

```bash
# 核心依赖（必需）
pip install cryptography psutil

# GUI依赖（可选）
pip install PyQt6
# 或者
pip install PySide6

# salsa20_stream 及所有含 salsa20 的配置必需；缺失则这些配置不可用
pip install PyNaCl

# 图像处理（可选）
pip install Pillow
```

### 基本使用

#### 图形界面模式
```bash
python main.py --gui
```

#### 命令行模式
```bash
# 加密文件
python main.py --cli -i myfile.txt -o ./encrypted

# 加密文件夹
python main.py --cli -i ./myfolder -o ./encrypted -p high

# 查看可用配置
python main.py --cli --list-profiles
```

#### 增强CLI模式
```bash
# 基础加密
python -m cli.enhanced_cli encrypt -i file.txt -o ./output

# 批量处理
python -m cli.enhanced_cli batch -d ./documents -o ./encrypted

# 系统信息
python -m cli.enhanced_cli info --system
```

## 📖 详细文档

- [用户手册](user_guide.md) - 详细的使用指南
- [开发文档](developer_guide.md) - 开发者参考
- [API文档](api_reference.md) - API接口说明
- [配置指南](configuration.md) - 配置文件说明
- [故障排除](troubleshooting.md) - 常见问题解决

## 🔧 配置文件

系统支持多种预定义的加密配置：

- **basic**: 基础加密（AES-256-GCM）
- **standard**: 标准加密（ChaCha20 + AES-256-CBC）
- **high**: 高级加密（RSA + ChaCha20 + AES-256-GCM + 自定义算法）
- **stealth**: 隐蔽加密（包含隐写术）
- **paranoid**: 偏执级加密（最高安全级别）

## 🎯 使用场景

### 个人用户
- 重要文档加密
- 隐私文件保护
- 备份数据加密

### 企业用户
- 敏感数据保护
- 文档传输加密
- 合规性要求

### 开发者
- 软件保护
- 数据库加密
- API密钥保护

## 🔍 系统要求

- **操作系统**: Windows 10+, Linux, macOS
- **Python版本**: 3.8+
- **内存**: 最少512MB，推荐2GB+
- **存储**: 100MB可用空间

## 📊 性能指标

| 算法 | 小文件(1MB) | 中文件(100MB) | 大文件(1GB) |
|------|-------------|---------------|-------------|
| AES-256-GCM | ~2ms | ~200ms | ~2s |
| ChaCha20 | ~1.5ms | ~150ms | ~1.5s |
| RSA-2048 | ~50ms | N/A* | N/A* |

*RSA仅用于小数据或密钥加密

## 🤝 贡献指南

欢迎贡献代码！请查看 [贡献指南](CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

如果遇到问题：

1. 查看 [故障排除](troubleshooting.md)
2. 搜索已有的 [Issues](https://github.com/your-repo/issues)
3. 创建新的 Issue

## 🔄 更新日志

### v1.0.0 (2025-06-20)
- ✨ 初始版本发布
- 🔐 支持多种加密算法
- 🖥️ 图形界面和命令行界面
- ⚡ 性能优化和大文件支持
- 🛡️ 安全保护机制
- 📚 完整文档系统

## 🙏 致谢

感谢以下开源项目：
- [cryptography](https://cryptography.io/) - 加密库
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI框架
- [psutil](https://psutil.readthedocs.io/) - 系统信息

---

**⚠️ 重要提醒**: 请妥善保管解密器文件，丢失后将无法恢复加密数据！
