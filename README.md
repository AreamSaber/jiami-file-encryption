# jiami · 文件与目录加密

Python 文件加密项目，提供 CLI、现有 GUI 和可配置的加密流程。v1 使用经过认证的数据格式，并将密文与恢复密钥分开保存。已完成对 `00833fb` 的 Linux CPU 人工代码审查，后续清理见 [审查记录](docs/reviews/2026-09-23-v1-manual-review.md)。这不是密码学安全认证。

## 快速开始（Linux CPU）

需要 Python 3.12、[uv](https://docs.astral.sh/uv/) 和 C 编译器。Debian/Ubuntu 可安装 `build-essential`；真实 Twofish 原生库需要编译。

```bash
python3 tools/dev.py setup
.venv/bin/python tools/dev.py doctor
.venv/bin/python main.py --cli --list-profiles
.venv/bin/python main.py --cli -i example.txt -o ./encrypted -p basic
.venv/bin/python encrypted/example.txt.jiami/recover.py encrypted/example.txt.jiami/data.jmi ./restored.txt
.venv/bin/python tools/dev.py test
```

目录输入使用同一命令；输出目录必须在输入目录之外。恢复目标必须是尚不存在的路径。

## 输出与密钥保管

每个输入生成一个完整目录，例如 `example.txt.jiami/`：

| 文件 | 用途 | 能否分享 |
|---|---|---|
| `data.jmi` | 经认证的密文和公开元数据 | 可以；仍会公开原文件名、大小和配置名称 |
| `recovery.jmis` | 恢复密钥、私密元数据、认证密钥 | 必须保密 |
| `recover.py` | 带恢复秘密的独立 Python 程序 | 必须保密 |
| `PRIVATE-README.txt` | 操作说明 | 不要因此分享整个目录 |

**只分享 `data.jmi`。不要打包、上传或发送整个 `.jiami` 目录。** 恢复材料当前不受口令保护。丢失恢复材料就无法恢复；泄露它等同于泄露密钥。

独立恢复程序携带本项目的恢复源码，仍需要 Python 和相应算法依赖。可在仓库之外执行；不是无需运行时的 EXE。Windows EXE 构建接口需在具备 Twofish 原生编译环境及 PyInstaller 的 Windows 上单独验收。

## 当前支持范围

- 全部 11 个出厂配置：`basic`、`standard`、`high`、`stealth`、`paranoid`、`parallel_fast`、`blowfish_secure`、`salsa20_stream`、`twofish_strong`、`multi_algorithm`、`paranoid_gpu`。
- v1 默认使用 CPU 标准算法路径，保留分层、多线程分块和并行分片拓扑。`paranoid_gpu` 是保留的配置名称，不表示已经使用 GPU。
- Twofish 使用 `twofish==0.3.0` 的真实原生实现；Python 3.12 兼容绑定位于 `src/crypto/twofish_backend.py`。Salsa20 配置使用 PyNaCl SecretBox 的具体变体。缺少依赖会明确失败，不替换成其他密码算法。
- RSA 档位保留，私钥只存在于恢复材料中。本阶段没有收件人公钥投递，也没有 PBKDF2/Argon2 口令加密。
- 多层和自定义混淆不代表额外安全强度；隐写层不保证密文不可识别。
- GPU 后端仅保留显式适配接口；旧实验内核不会自动用于 v1。GPU 真机、完整桌面 GUI 和 Windows EXE 尚需单独验收。

## 格式和文件保护

新入口仅接受 `JMI1` / `JMIS` v1，拒绝旧 pickle。旧文件迁移是独立工作，不提供不安全的读取开关。

读取先检查长度和版本，再认证原始字节，最后解析 JSON、校验完整恢复计划并解密。恢复后的长度和 SHA-256 必须符合私密记录，验证通过前不会发布明文。

加密先写入同目录下独立的私密暂存目录，验证后一次重命名发布，默认不覆盖。冲突或发布前失败会保留该次暂存目录；没有自动接管、重试覆盖或续传。Linux 使用 `renameat2(RENAME_NOREPLACE)`，不支持时明确失败；跨文件系统不自动复制。

重命名后父目录同步失败会报告「已发布，持久性未确认」，保留完整输出。Windows 的发布不承诺断电持久性，要求 Python 3.12.4+ 和支持访问控制的本地文件系统；暂存目录仅向当前用户与管理员开放。

本版本的引擎在内存中工作：单帧密文/目录归档上限 1 GiB，单个 JSON 头上限 1 MiB。这不是流式大文件实现，实际可处理规模取决于内存及档位膨胀比例；长操作记录可能先达到头大小限制。

## 开发与验证

完整 CPU 测试使用 `.venv/bin/python tools/dev.py test`。`test-core` 只是配置/异常子集。GPU 设备缺失的测试应明确记录跳过原因；Linux 通过不代表 Windows EXE、GPU 或 GUI 已通过。

- [架构与模块边界](docs/architecture.md)
- [v1 协议、信任模型与发布约定](docs/security-redesign.md)
- [远程开发与人工 Claude 交接](docs/remote-development.md)

`docs/` 中其余历史手册、根目录历史调试/打包脚本可能仍描述旧格式；不能作为 v1 支持承诺或旧文件迁移工具。以本页和上述三份文档为准。

## 许可证

项目遵循仓库 LICENSE。Twofish Python 绑定的上游许可见 `src/crypto/TWOFISH-LICENSE.txt`；生成的恢复程序包含该许可。
