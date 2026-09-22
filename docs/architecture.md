# 架构与开发边界

本文件基于仓库代码结构和首次 Claude 架构建议整理，描述现状，不是密码学安全认证。

| 部分 | 代码位置 | 主要职责 | 验证位置 |
|---|---|---|---|
| 算法实现 | `src/crypto/` | 标准算法与自定义变换 | Linux CPU；GPU特例另验 |
| 流程编排 | `src/encryptor/`、`src/decryptor/` | 分层流程、文件处理、解密器生成 | Linux CPU + Windows |
| 交互入口 | `main.py`、`cli/`、`gui/` | 命令行与图形界面 | CLI 可远程；GUI 在本机 |
| 并行与硬件 | `src/thread_pool/`、`src/gpu/` | 线程调度、OpenCL/CUDA 检测与计算 | CPU 远程；GPU 真机 |
| 配置与错误 | `src/utils/config_manager.py`、`src/exceptions/` | 配置校验、统一错误 | Linux CPU |

模块间的完整运行关系尚不能验证：上游缺失 `src/encryptor/key_injector.py`
和 `src/decryptor/base_decryptor.py`，导致主入口导入失败，完整测试无法收集。

## 决策 001：远程主工作区，按提交审查

- 代码、依赖、终端和 CPU 测试统一放在 Linux 主工作区；本机 VS Code 负责显示和交互。
- Codex 实现和验证；Claude 设计并审查关键变更。当前由用户手动转交问题和答复，注明固定提交范围。
- 报告记录目标提交和比较基线。未提交修改不纳入报告，不能把旧报告当成新修改的批准。
- GitHub 用来保存提交和 PR；Windows GUI/GPU 验收按同一提交取代码，不做双向文件实时同步。
- 2GB 开发机先串行执行资源密集任务。是否升级内存由实际使用情况决定。

代价：Windows GUI/GPU 仍要单独验收；大型构建/并行 AI 会受内存限制。
替代方案：全本机开发会增加远程 Claude 的上下文传递步骤；双向同步会增加冲突处理。

## 后续优先事项

1. 找回缺失源码并修正忽略规则，恢复完整测试收集。
2. 再记录加解密往返、失败后文件完整性、历史密文兼容性的真实验证结果。
3. 涉及算法、密钥处理、格式变更、线程/GPU边界时先形成方案，再由 Codex 实现。

## 决策 002：安全重构范围与人工交接

用户已确认的四项产品范围及分阶段状态见 [安全重构决策](security-redesign.md)。
四个缺失模块仍需在协议细节确定后恢复；不自动调用 Claude。
