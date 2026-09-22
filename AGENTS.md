# 开发约定

本项目使用家宽 Linux 主工作区，VS Code 通过 SSH 打开；不做双向文件同步。
先读 `docs/remote-development.md` 和 `docs/architecture.md`。

- Codex 负责实现、依赖、测试、修复和整理文档；Claude 负责架构设计与关键变更审查。
- 小修复按已有架构直接实现；涉及加密格式、密钥处理、算法、线程/GPU边界或重大依赖时，先请 Claude 给方案。
- Claude 暂由用户手动接入：Codex 提供英文问题、固定提交范围及验证证据，用户转交并贴回答复；不要自动调用 Claude。
- 所有测试使用 `.venv`。`python tools/dev.py test-core` 是配置/异常子集，不代表完整加解密通过。
- 完整验证入口为 `python tools/dev.py test`；保留失败事实，不使用假模块、宽泛 skip 或放宽断言掩盖缺失源码。
- GUI、GPU 和 Windows 打包在合适的本机环境单独验收；Linux 通过不能代表这些平台通过。
- 不提交凭据、真实用户待加密文件、运行日志、生成的带密钥解密器或虚拟环境。
- 在工作分支完成变更和验证，生成可审查的 PR；不要自动合并。

当前已知阻塞：上游缺少 key_injector.py、base_decryptor.py、cpu_decryptor.py 和 gpu_decryptor.py。
用户已确认分阶段安全重构范围，见 `docs/security-redesign.md`。在协议细节明确前先完成独立修正，
不得用占位模块掩盖完整测试阻塞，也不得把已确认的产品范围误报为已经实现。
