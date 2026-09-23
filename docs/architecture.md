# 架构与开发边界

## v1 模块关系

| 部分 | 代码位置 | 职责 |
|---|---|---|
| 入口与生产者 | `main.py`、`src/encryptor/main.py`、`hybrid_engine.py` | 读取文件/目录，按配置生成密文及完整恢复元数据 |
| 协议 | `src/package_format/envelope.py`、`schema.py` | 限长帧、原始字节 MAC、封闭结构、公开/私密投影、完整计划验证 |
| 发布 | `src/package_format/writer.py`、`publication.py` | 私密暂存、真实读取器验证、一次不覆盖重命名、同步结果报告 |
| 目录 | `src/package_format/archive.py` | 数据型 ZIP_STORED 归档、路径/大小/类型校验 |
| 共享恢复 | `src/decryptor/base_decryptor.py`、`algorithm_registry.py` | 认证、校验拓扑、逐层/分片恢复、哈希检查、发布明文 |
| 恢复入口 | `cpu_decryptor.py`、`gpu_decryptor.py`、GUI/模板适配器 | 共享同一读取与发布流程；GPU 需显式后端 |
| 程序生成 | `src/encryptor/key_injector.py` | 将共享恢复源码及私密恢复帧装入独立 Python 程序；可选 Windows 构建接口 |

原来缺失的四个模块已经实现。恢复程序和模板不再各自维护一套密码算法。

## 算法与硬件边界

v1 默认 CPU 路径；AES GCM/CBC/CTR、ChaCha20、PyNaCl SecretBox、Blowfish、真实 Twofish、RSA/OAEP 或 RSA 混合模式及现有自定义变换都有明确变体与参数结构。标准依赖缺失会失败，不能改用简化算法。

多线程分层保存每个块各自的密钥与输入/输出长度；并行分片与逐层流水线是不同拓扑，不隐式互换。GPUDecryptor 只向显式提供的 backend 调用 `supports`/`decrypt`，是否允许 CPU 回退由调用者选择并记录实际使用情况；GPUFileEncryptor 无已验证后端时明确报告 CPU 回退。算法运行失败不通过回退伪装成成功。

现有实验 GPU 代码仍留在仓库中，未纳入 v1 默认协议实现。`config/gpu_optimized_profiles.json` 已标记过时；支持清单以 `config/encryption_profiles.json` 的 11 项为准。

## 决策：按提交人工审查

代码、终端和 CPU 验证放在 Linux 工作区；VS Code 通过 SSH 操作。Codex 实现和验证，Claude 设计与审查；用户手动转交固定提交范围、英文问题和测试证据，不自动调用 Claude。

本次实现使用独立 worktree，保留 Claude 原有 checkout。打开对应实现 worktree 的 `jiami-remote.code-workspace` 即可开发。GitHub PR 保存可审查提交，不自动合并。Windows GUI/GPU 按相同提交另验，不做双向实时同步。

协议与信任模型见 [安全重构决策](security-redesign.md)。

## 批量任务与 Qt 工作线程

BatchProcessor 的 FileEncryptor 只作为配置模板。每个文件任务获得独立的线程配置快照与加密器，在 finally 中关闭自己的线程池。外层任务数受请求值、文件数和有效线程预算共同限制；每个内层池分配预算的整数份额。外层调度线程不包含在内层预算中；这不是内存上限。其他入口仍保留全局线程管理器的兼容默认行为。

主 Qt 窗口的解密入口直接使用 CPUDecryptor 处理 data.jmi/包目录与 recovery.jmis，不执行恢复脚本。窗口一次只运行一个任务，收到真实 QThread.finished 后才释放引用与恢复操作按钮；关闭期间不会强行终止写入线程。当前没有安全取消或流式进度百分比。

旧的 LargeFileProcessor、MemoryManager、ProgressTracker、InterruptController 和未使用的临时文件辅助方法已移除。它们没有接入 v1 发布流程，不能作为流式大文件支持依据。实际测量见 [内存记录](memory-profile.md)。
