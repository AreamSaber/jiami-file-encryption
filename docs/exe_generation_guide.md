# exe解密器生成指南

本指南将帮助您解决exe解密器生成问题，并提供多种解决方案。

## 🔍 问题诊断

如果您遇到"此应用无法在你的电脑上运行"的错误，可能的原因包括：

1. **PyInstaller未正确安装**
2. **PyInstaller不在系统PATH中**
3. **权限问题**
4. **系统环境问题**

## 🛠️ 解决方案

### 方案1：检查和安装PyInstaller

```bash
# 检查PyInstaller是否安装
pyinstaller --version

# 如果未安装，请安装
pip install pyinstaller

# 如果安装失败，尝试升级pip
python -m pip install --upgrade pip
pip install pyinstaller
```

### 方案2：使用手动打包工具

我们提供了专门的手动打包工具：

```bash
# 查找所有解密器
python tools/manual_packager.py --list

# 打包指定目录中的所有解密器
python tools/manual_packager.py -d ./encrypted_output

# 打包指定文件
python tools/manual_packager.py -f ./encrypted_output/myfile_decryptor.py
```

### 方案3：使用批处理文件（Windows）

如果PyInstaller无法工作，系统会自动生成批处理文件：

1. 查找 `*_decryptor.bat` 文件
2. 双击运行批处理文件
3. 按提示输入加密文件和输出路径

### 方案4：直接运行Python脚本

```bash
# 直接运行Python解密器
python myfile_decryptor.py encrypted_file.encrypted output_file.txt
```

## 🔧 手动生成exe文件

如果自动生成失败，您可以手动生成：

### 步骤1：找到Python解密器文件

解密器文件通常命名为 `*_decryptor.py`，位于加密输出目录中。

### 步骤2：使用PyInstaller手动打包

```bash
# 基本命令
pyinstaller --onefile --console your_decryptor.py

# 指定输出目录
pyinstaller --onefile --console --distpath ./output your_decryptor.py

# 指定exe名称
pyinstaller --onefile --console --name MyDecryptor your_decryptor.py
```

### 步骤3：测试生成的exe文件

```bash
# 测试exe文件
./dist/your_decryptor.exe encrypted_file.encrypted output_file.txt
```

## 🐛 常见问题解决

### 问题1：PyInstaller命令未找到

**解决方案**：
```bash
# 使用完整路径
python -m PyInstaller --onefile --console your_decryptor.py

# 或者重新安装
pip uninstall pyinstaller
pip install pyinstaller
```

### 问题2：权限被拒绝

**解决方案**：
- 以管理员身份运行命令提示符
- 检查文件夹权限
- 尝试在不同目录中操作

### 问题3：生成的exe无法运行

**解决方案**：
```bash
# 添加调试信息
pyinstaller --onefile --console --debug all your_decryptor.py

# 检查依赖
pyinstaller --onefile --console --hidden-import cryptography your_decryptor.py
```

### 问题4：exe文件过大

**解决方案**：
```bash
# 排除不必要的模块
pyinstaller --onefile --console --exclude-module matplotlib your_decryptor.py

# 使用UPX压缩（需要先安装UPX）
pyinstaller --onefile --console --upx-dir /path/to/upx your_decryptor.py
```

## 📋 完整的手动打包脚本

创建一个批处理文件 `build_exe.bat`：

```batch
@echo off
echo 🔧 手动生成exe解密器
echo ========================

set /p PYTHON_FILE="请输入Python解密器文件路径: "

if not exist "%PYTHON_FILE%" (
    echo ❌ 文件不存在: %PYTHON_FILE%
    pause
    exit /b 1
)

echo 🚀 开始打包...
pyinstaller --onefile --console "%PYTHON_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo ✅ 打包成功！
    echo 📁 exe文件位于 dist 目录中
) else (
    echo ❌ 打包失败！
    echo 💡 请检查PyInstaller安装和Python文件
)

pause
```

## 🎯 推荐工作流程

1. **首次使用**：
   ```bash
   pip install pyinstaller
   python main.py --cli -i myfile.txt -o ./encrypted
   ```

2. **如果自动生成失败**：
   ```bash
   python tools/manual_packager.py -d ./encrypted
   ```

3. **如果手动打包也失败**：
   - 使用生成的批处理文件
   - 或直接运行Python脚本

4. **验证结果**：
   ```bash
   ./encrypted/myfile_decryptor.exe ./encrypted/myfile.encrypted ./decrypted.txt
   ```

## 💡 最佳实践

1. **环境准备**：
   - 确保Python 3.8+
   - 安装所有必需依赖
   - 使用虚拟环境

2. **文件管理**：
   - 保持文件路径简短
   - 避免特殊字符
   - 使用英文路径

3. **测试验证**：
   - 在不同机器上测试exe
   - 验证解密功能
   - 检查文件完整性

## 🆘 获取帮助

如果仍然遇到问题：

1. 检查系统日志
2. 运行诊断命令：
   ```bash
   python tools/manual_packager.py --help
   python -c "import PyInstaller; print('PyInstaller可用')"
   ```
3. 提供详细的错误信息

---

**注意**：生成的exe文件包含解密密钥，请妥善保管！
