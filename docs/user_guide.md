# 用户手册

本手册将详细介绍如何使用文件加密系统的各项功能。

## 📋 目录

1. [安装和设置](#安装和设置)
2. [图形界面使用](#图形界面使用)
3. [命令行使用](#命令行使用)
4. [加密配置](#加密配置)
5. [高级功能](#高级功能)
6. [常见问题](#常见问题)

## 🔧 安装和设置

### 系统要求

- Python 3.8 或更高版本
- Windows 10+, Linux, 或 macOS
- 至少 512MB 可用内存
- 100MB 可用磁盘空间

### 安装步骤

1. **下载项目**
   ```bash
   git clone https://github.com/your-repo/file-encryption-system.git
   cd file-encryption-system
   ```

2. **安装依赖**
   ```bash
   # 核心依赖
   pip install cryptography psutil
   
   # GUI支持（选择其一）
   pip install PyQt6
   # 或
   pip install PySide6
   
   # 可选扩展
   pip install pycryptodome PyNaCl Pillow
   ```

3. **验证安装**
   ```bash
   python main.py --help
   ```

## 🖥️ 图形界面使用

### 启动GUI

```bash
python main.py --gui
```

### 主界面功能

#### 文件加密标签页

1. **选择文件或文件夹**
   - 点击"浏览..."按钮选择要加密的文件或文件夹
   - 支持单个文件或整个文件夹加密

2. **选择输出目录**
   - 点击"浏览..."按钮选择加密文件的保存位置

3. **选择加密配置**
   - 从下拉菜单中选择预定义的加密配置
   - 可选择：basic, standard, high, stealth, paranoid

4. **开始加密**
   - 点击"开始加密"按钮
   - 观察进度条和状态信息
   - 加密完成后会显示结果

#### 文件解密标签页

- 查看可用的解密器列表
- 获取解密说明和指导

#### 设置标签页

- 查看系统信息
- 配置程序选项
- 管理加密配置

### 高级选项

勾选"显示高级选项"可以访问：
- 自定义加密参数
- 压缩设置
- 隐写术选项
- 安全保护设置

## 💻 命令行使用

### 基础命令行模式

#### 加密文件
```bash
python main.py --cli -i myfile.txt -o ./encrypted
```

#### 加密文件夹
```bash
python main.py --cli -i ./myfolder -o ./encrypted -p high
```

#### 查看可用配置
```bash
python main.py --cli --list-profiles
```

### 增强命令行模式

#### 基础加密
```bash
python -m cli.enhanced_cli encrypt -i file.txt -o ./output
```

#### 批量处理
```bash
# 处理目录中的所有文件
python -m cli.enhanced_cli batch -d ./documents -o ./encrypted

# 递归处理子目录
python -m cli.enhanced_cli batch -d ./documents -o ./encrypted --recursive

# 并行处理（4个线程）
python -m cli.enhanced_cli batch -d ./documents -o ./encrypted --parallel 4

# 试运行（不实际加密）
python -m cli.enhanced_cli batch -d ./documents -o ./encrypted --dry-run
```

#### 配置管理
```bash
# 列出所有配置
python -m cli.enhanced_cli config --list

# 显示配置详情
python -m cli.enhanced_cli config --show standard

# 创建新配置
python -m cli.enhanced_cli config --create myconfig

# 导出配置
python -m cli.enhanced_cli config --export standard ./my_config.json
```

#### 系统信息
```bash
# 显示系统信息
python -m cli.enhanced_cli info --system

# 检查依赖包
python -m cli.enhanced_cli info --dependencies

# 显示可用算法
python -m cli.enhanced_cli info --algorithms
```

#### 实用工具
```bash
# 性能基准测试
python -m cli.enhanced_cli tools --benchmark ./testfile.dat

# 验证文件完整性
python -m cli.enhanced_cli tools --verify ./encrypted_file.encrypted

# 生成随机密钥
python -m cli.enhanced_cli tools --generate-key 32
```

## ⚙️ 加密配置

### 预定义配置

#### basic - 基础加密
- **算法**: AES-256-GCM
- **安全级别**: 1
- **适用场景**: 一般文件保护
- **性能**: 快速

#### standard - 标准加密
- **算法**: ChaCha20 + AES-256-CBC
- **安全级别**: 2
- **适用场景**: 平衡安全性和性能
- **性能**: 中等

#### high - 高级加密
- **算法**: RSA-4096 + ChaCha20 + AES-256-GCM + 自定义算法
- **安全级别**: 3
- **适用场景**: 敏感数据保护
- **性能**: 较慢

#### stealth - 隐蔽加密
- **算法**: AES-256-GCM + 矩阵密码 + 隐写术
- **安全级别**: 3
- **适用场景**: 数据隐藏和加密结合
- **性能**: 很慢

#### paranoid - 偏执级加密
- **算法**: 多层复合加密
- **安全级别**: 5
- **适用场景**: 最高级别的安全保护
- **性能**: 极慢

### 自定义配置

可以通过配置管理功能创建自定义配置：

```bash
python -m cli.enhanced_cli config --create myconfig
```

按照提示输入：
- 显示名称和描述
- 安全级别
- 加密算法
- 可选功能（压缩、隐写术等）

## 🔍 高级功能

### 大文件处理

系统自动优化大文件处理：
- **分块处理**: 大文件自动分块处理
- **内存管理**: 智能内存使用控制
- **进度显示**: 实时进度和速度显示
- **并行处理**: 多线程并行加密

### 批量处理

支持批量处理多个文件：
- **模式匹配**: 使用通配符选择文件
- **排除模式**: 排除特定文件
- **递归处理**: 处理子目录
- **并行执行**: 多线程并行处理

### 隐写术

支持将加密数据隐藏在其他文件中：
- **图像隐写**: LSB图像隐写
- **文本隐写**: 空白字符隐写
- **音频隐写**: 音频LSB隐写

### 安全保护

解密器包含多种安全保护机制：
- **反调试**: 检测调试器
- **反虚拟机**: 检测虚拟环境
- **代码混淆**: 保护程序逻辑
- **完整性检查**: 验证文件完整性

## 🔓 解密文件

### 使用解密器

1. **找到解密器**
   - 解密器文件位于加密输出目录
   - 文件名格式：`原文件名_decryptor.exe`

2. **运行解密器**
   ```bash
   python decryptor.exe encrypted_file.encrypted output_file.txt
   ```

3. **验证结果**
   - 检查解密后的文件
   - 验证文件完整性

### 解密器特点

- **自包含**: 包含所有必要的密钥和算法
- **独立运行**: 不依赖原加密程序
- **安全保护**: 内置多种安全机制
- **跨平台**: 支持多种操作系统

## ❓ 常见问题

### Q: 忘记了解密器文件怎么办？
A: 解密器文件是恢复数据的唯一方式，请务必妥善保管。建议：
- 将解密器备份到多个位置
- 使用云存储备份
- 记录解密器的存放位置

### Q: 可以修改加密后的文件吗？
A: 不可以。任何修改都会导致解密失败。加密文件包含完整性检查。

### Q: 支持哪些文件类型？
A: 支持所有类型的文件和文件夹，包括：
- 文档文件（PDF, DOC, TXT等）
- 图像文件（JPG, PNG, GIF等）
- 视频文件（MP4, AVI, MKV等）
- 压缩文件（ZIP, RAR, 7Z等）
- 程序文件（EXE, DLL等）

### Q: 加密会压缩文件吗？
A: 可选。某些配置包含压缩功能，可以减小文件大小。

### Q: 如何提高加密速度？
A: 可以：
- 选择较快的加密配置（如basic）
- 使用并行处理
- 增加系统内存
- 使用SSD存储

### Q: 系统崩溃了怎么办？
A: 只要解密器文件完整，就可以恢复数据。建议：
- 定期备份解密器
- 使用稳定的存储设备
- 避免在加密过程中强制关机

### Q: 可以在其他电脑上解密吗？
A: 可以。解密器是自包含的，可以在任何支持Python的系统上运行。

---

如需更多帮助，请查看 [故障排除](troubleshooting.md) 或联系技术支持。
