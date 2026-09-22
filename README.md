# jiami · 多层混合文件加密系统

<div align="center">

**Python 实现的企业向文件加密工程**

CLI · GUI · 多层算法流水线 · CPU/GPU 引擎 · 自包含解密器

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#许可证)
[![Crypto](https://img.shields.io/badge/Crypto-AES%20%7C%20ChaCha20%20%7C%20RSA%20%7C%20Twofish-orange.svg)](#算法库)
[![Accel](https://img.shields.io/badge/Accel-CPU%20%2B%20OpenCL%20GPU-purple.svg)](#计算引擎)

</div>

---

## 项目是什么

`jiami` 是一套**双端架构**的文件加密系统：

| 角色 | 职责 |
|------|------|
| **加密端（Encryptor）** | 对文件/目录做多层混合加密，输出密文 + **自包含解密器**（密钥与元数据注入） |
| **解密端（Decryptor）** | 由加密端生成的专用解密程序/模板，按层逆序恢复明文；支持 CPU / GPU / 混合 GUI |

核心不是「单一算法封装」，而是：

1. **可配置的多层加密流水线**（JSON Profile）
2. **算法注册表 + 统一加解密接口**
3. **线程池自适应分块并行**
4. **可选 GPU（OpenCL）加速路径**
5. **安全配置**（密钥派生、混淆、反调试等策略项）

---

## 功能一览

### 加密能力

- 单文件 / 整目录批量加密
- **预设安全档位**：`basic` → `standard` → `high` → `stealth` → `paranoid` 等
- 层间可自由组合：对称流/分组密码、非对称、自定义混淆、隐写
- 加密完成后可生成 **带密钥的解密器**，便于离线交付
- 大文件分块、进度回调、可中断控制

### 解密能力

- 基类 `BaseDecryptor` + 算法注册表，**按层逆序**解密
- CPU 解密器 / GPU 解密器 / 混合 GUI 解密器
- 模板化生成（`cpu_template` / `gpu_template` / 通用 `template`）
- 独立启动入口：`decryptor_launcher.py`、`gpu_decryptor_gui.py` 等

### 交互方式

| 模式 | 启动方式 | 说明 |
|------|----------|------|
| 分离式引擎 GUI（默认） | `python main.py` 或 `python main.py --separate` | 推荐日常使用 |
| 传统 GUI | `python main.py --gui` | PyQt6 / PySide6 主窗口 |
| 命令行 | `python main.py --cli -i <路径> -o <目录> -p <档位>` | 脚本与批处理友好 |
| 自检 | `python main.py --test` / `--test-cpu` / `--test-gpu` | 引擎连通与对比 |

### 工程化

- JSON Schema 校验配置（`config/schemas/`）
- 结构化异常体系（加密/解密/配置错误码）
- 单元测试 + 集成测试 + Hypothesis 属性测试
- Docker 镜像（含 OpenCL 头文件/开发包，便于 GPU 相关环境）
- 文档目录：用户手册、开发者指南、GUI/解密器/打包说明

---

## 算法库

### 标准密码学算法

| 算法 | 模块 | 要点 |
|------|------|------|
| **AES-128/192/256** | `src/crypto/aes_encryption.py` | 支持 **GCM / CBC / CTR**；GCM 带认证标签 |
| **ChaCha20** | `src/crypto/chacha20_encryption.py` | 现代流密码，适合软件实现 |
| **Salsa20** | `src/crypto/salsa20_encryption.py` | 流密码族 |
| **Blowfish** | `src/crypto/blowfish_encryption.py` | 经典分组密码 |
| **Twofish** | `src/crypto/twofish_encryption.py` | AES 竞赛候选算法 |
| **RSA** | `src/crypto/rsa_encryption.py` | 大密钥（配置中可达 4096），OAEP 填充 |
| **隐写术** | `src/crypto/steganography.py` | 图像 LSB 等（依赖 Pillow/NumPy，可降级） |

依赖侧：`cryptography`（主）、`pycryptodome`、`pynacl`（可选扩展）。

### 自定义混淆 / 古典扩展

`CustomAlgorithms`（`src/crypto/custom_algorithms.py`）提供可组合的混淆层，用于抬高分析成本（**不替代** AES/ChaCha 等主保密性算法）：

| 名称 | 作用 |
|------|------|
| Simple XOR | 字节级异或 |
| Bit Shuffle | 位级置换（可多种子轮次） |
| Rotate Cipher | 字节旋转 |
| Substitution Cipher | 替换表 |
| Multi-layer 组合 | 多层自定义算法串联 |
| 配置中的 matrix / pre_scramble 等 | 在 high / stealth / paranoid 档位中出现 |

### 密钥与完整性校验（当前能力）

- 主加密流程使用随机密钥。`CryptoUtils.derive_key()` 虽提供 PBKDF2 工具函数，
  但未接入主流程；PBKDF2、scrypt、Argon2 不是当前可选的口令加密功能。
- 配置及 GUI 已移除未生效的口令派生／迭代次数选项。
- `src/security/anti_reverse.py` 仅保留 SHA-256 文件校验。调用者必须提供可信来源的
  预期哈希；没有预期值、文件不可读或内容不匹配时返回失败。该函数不自动接入加解密流程。
- 反调试、反虚拟机、分析工具检测、干扰代码已移除；普通文件哈希不等于软件来源认证。

当前旧格式仍存在将解密材料随密文保存的问题，完整加解密也因缺失模块尚未恢复。
密钥分离、认证容器、拒绝旧 pickle 和默认不覆盖的产品范围已确认，实施状态见
[安全重构决策](docs/security-redesign.md)。本次配置修正不代表新格式已经上线。
`security_settings.json` 其余历史策略字段也不能作为功能已接入的证明。

---

## 加密配置档位（Profiles）

配置文件：`config/encryption_profiles.json`  
GPU 优化档：`config/gpu_optimized_profiles.json`

| Profile | 名称 | 层级概要 | 适用场景 |
|---------|------|----------|----------|
| `basic` | 基础加密 | AES-256-GCM 单层 | 一般文件、追求速度 |
| `standard` | 标准加密 | ChaCha20 → AES-256-CBC | 日常平衡档（CLI 默认） |
| `high` | 高级加密 | RSA-4096 → ChaCha20 → AES-GCM → bit_shuffle | 敏感数据 |
| `stealth` | 隐蔽加密 | AES-GCM → matrix_cipher → 图像隐写 | 需隐藏密文形态 |
| `paranoid` | 偏执级 | 预打乱 + RSA + AES(高迭代) + ChaCha20 + 多轮自定义… | 最高配置、成本最高 |
| `parallel_fast` | 并行快速 | 面向吞吐的线程策略 | 大文件快速处理 |
| `blowfish_secure` / `salsa20_stream` / `twofish_strong` | 单算法强化档 | 对应算法为主 | 算法专项场景 |
| `multi_algorithm` | 多算法 cascade | 多种对称算法串联 | 算法多样性 |
| `paranoid_gpu` 等 | GPU 向偏执/高级 | 配合 `enable_gpu`、阈值与首选算法 | 大文件 + 有 OpenCL 设备 |

每档可单独配置：

- `layers[]`：方法、模式、密钥长度、迭代/轮次等
- `threading`：是否自动多线程、最大线程、并行阈值（MB）
- `gpu_settings`：是否启用 GPU、阈值、优先算法列表
- `performance`：速度/内存占用标签

Schema 校验：`config/schemas/encryption_profiles.schema.json`、`security_settings.schema.json`。

---

## 计算引擎与并行

```text
                    ┌─────────────────────┐
   输入文件/目录 ──►│   FileEncryptor      │
                    │  (src/encryptor)     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     PureCPUEngine    HybridEngine      PureGPU / GPUFile
     pure_cpu_*.py    hybrid_engine.py  pure_gpu_*.py
              │                │                │
              └────────┬───────┴───────┬────────┘
                       ▼               ▼
              ThreadManager      GPUManager (OpenCL)
              分块 / 线程池       设备选择 / 强制 CPU 回退
```

要点：

- **HybridEncryptionEngine**：注册 `aes256` / `chacha20` / `salsa20` / `blowfish` / `twofish` / `rsa` / `custom` / `steganography` 等方法，支持分层与并行
- **ThreadManager**：按数据规模与算法推荐线程数；大文件自动抬高 chunk（如 ≥100MB 使用更大块以降低调度开销）
- **GPU**：`src/gpu/gpu_manager.py`、AMD 原型、`gpu_file_encryptor`；启动时 `main.py` 可自动设置 `PYOPENCL_CTX`
- 性能工具：`src/performance/`（benchmark、大文件处理器、内存管理、进度跟踪）

---

## 架构与目录

```text
jiami/
├── main.py                      # 统一入口：CLI / GUI / 自检
├── requirements.txt
├── setup.py                     # 可安装包元数据
├── Dockerfile                   # Python + OpenCL 基础环境
├── config/
│   ├── encryption_profiles.json # 加密档位
│   ├── gpu_optimized_profiles.json
│   ├── security_settings.json   # 安全与性能策略
│   └── schemas/                 # JSON Schema
├── src/
│   ├── crypto/                  # 算法实现
│   ├── encryptor/               # 加密主流程与多引擎
│   ├── decryptor/               # 解密基类、注册表、CPU/GPU/GUI
│   ├── gpu/                     # OpenCL / 设备管理
│   ├── thread_pool/             # 全局线程管理
│   ├── performance/             # 压测与大文件
│   ├── security/                # 反逆向等
│   ├── exceptions/              # 分层错误类型
│   └── utils/                   # 日志、配置、文件与密码学工具
├── gui/                         # PyQt6 主窗口与加密对话框
├── cli/                         # 增强 CLI、批处理、配置管理
├── tests/
│   ├── unit/                    # 注册表、配置、异常、基类
│   ├── integration/             # 混合引擎、加解密场景、线程
│   └── property/                # Hypothesis：往返、序列化、GPU 等
├── docs/                        # 用户/开发/GUI/打包文档
└── tools/                       # 诊断、打包辅助
```

### 关键数据流（加密）

1. 读取 Profile → 解析 `layers`
2. 对文件分块（可选并行）
3. **按层正向**应用算法，每层产生元数据（密钥、IV、tag、自定义参数等）
4. 汇总元数据，注入解密器模板或写出伴随结构
5. 输出密文与可独立运行的解密端

### 关键数据流（解密）

1. 加载元数据（文件内嵌 / 解密器全局注入）
2. `AlgorithmRegistry` 解析每层 `algorithm`
3. **`reversed(layers)` 逆序**调用对应 `handler.decrypt`
4. 写出明文；失败时抛出带 `error_code` 的 `DecryptionError`

---

## 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.10–3.12；仓库含 3.13 Docker 示例）
- Windows / Linux / macOS
- 可选：支持 OpenCL 的 GPU 驱动（GPU 路径）

### 安装

```powershell
cd jiami   # 或本仓库根目录

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
# GUI（二选一即可）
pip install PyQt6
```

核心依赖摘要：

| 包 | 用途 |
|----|------|
| cryptography / pycryptodome / pynacl | 密码学原语 |
| PyQt6 | 图形界面 |
| Pillow / numpy | 图像隐写与数值 |
| psutil / loguru / pyyaml / jsonschema | 系统、日志、配置 |
| pytest / hypothesis | 测试 |
| （可选）pyopencl | GPU |

### 运行

```powershell
# 查看帮助
python main.py --help

# 列出加密档位
python main.py --cli --list-profiles

# 命令行加密（示例）
python main.py --cli -i .\path\to\file.zip -o .\out -p standard -v

# 图形界面
python main.py --gui
# 或默认分离式界面
python main.py --separate

# 引擎自检
python main.py --test-cpu
python main.py --test-gpu
python main.py --test-both
```

### 测试

```powershell
pytest tests/unit -q
pytest tests/integration -q
pytest tests/property -q
```

根目录另有若干 `test_*.py` 脚本，用于轮次、混淆、GPU roundtrip、安全档位等专项验证。

### Docker

```powershell
docker build -t jiami-encryption .
docker run --rm -it jiami-encryption python main.py --help
```

镜像基于 `python:3.13-slim`，并安装 OpenCL 开发头文件以便编译/链接 GPU 相关组件。

---

## 使用提示

1. **档位选择**：日常用 `standard`；机密材料用 `high`；需隐藏密文外观用 `stealth`；`paranoid` 极慢且资源占用高。
2. **大文件**：打开对应 profile 的 `auto_threading`，并视情况启用 GPU 阈值（`gpu_threshold_mb`）。
3. **密钥安全**：生产环境务必更换默认 `SECRET`/派生参数；不要把真实密钥或密文样例提交到公开仓库。
4. **解密器交付**：将生成的解密端与密文一并交付时，注意渠道保密；解密器内嵌密钥意味着**持有解密器即可解密**。
5. **依赖缺失**：`main.py` 会区分核心依赖（`cryptography`）与可选依赖（`pycryptodome` / `PyNaCl` / `Pillow`），缺少可选包时仍可运行子集功能。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/user_guide.md](docs/user_guide.md) | 安装、GUI、CLI、配置与 FAQ |
| [docs/developer_guide.md](docs/developer_guide.md) | 开发与扩展 |
| [docs/gui_usage_guide.md](docs/gui_usage_guide.md) | GUI 专项 |
| [docs/decryptor_gui_guide.md](docs/decryptor_gui_guide.md) | 解密器 GUI |
| [docs/integrated_decryptor_guide.md](docs/integrated_decryptor_guide.md) | 集成解密器 |
| [docs/exe_generation_guide.md](docs/exe_generation_guide.md) | 可执行文件生成 |
| [docs/pyinstaller_fix_complete.md](docs/pyinstaller_fix_complete.md) | PyInstaller 相关 |

---

## 设计原则（摘要）

1. **主保密性依赖标准算法**（AES-GCM、ChaCha20 等），自定义层用于混淆与多样性，而非单独承担全部安全。
2. **配置与代码分离**：档位、安全策略、Schema 可演进而不改核心引擎。
3. **加解密对称**：层顺序在解密端严格反转；算法名统一由注册表解析。
4. **可观测**：日志（loguru 封装）、进度、异常上下文（层号、算法名、错误码）。
5. **可测试**：往返属性测试 + 混合引擎集成测试，降低回归风险。

---

## 作者

- GitHub：[@AreamSaber](https://github.com/AreamSaber)
- Email：whk1085403136@gmail.com

## 许可证

未在仓库中另行声明时，默认仅供学习与研究使用。若 `setup.py` 中标注 MIT，以你最终发布声明为准。商用或再分发请先确认授权范围。

---

<div align="center">

**Encrypt once · Decrypt anywhere（在密钥与解密器可控的前提下）**

</div>
