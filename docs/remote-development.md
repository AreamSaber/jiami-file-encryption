# 远程开发使用说明

## 打开项目

在 Windows VS Code 连接 SSH 主机 `claude-home`，打开
`~/projects/jiami-file-encryption/jiami-remote.code-workspace`。
也可在本机终端运行：

```powershell
code --remote ssh-remote+claude-home /home/claude-dev/projects/jiami-file-encryption/jiami-remote.code-workspace
```

Codex 应用：设置 → 连接 → SSH → 添加 `claude-home`，然后添加这个主机上的仓库目录。
VS Code 已连接不表示 Codex 应用已添加同一主机，两者需各配置一次。

## 常用操作

在工作区按 `Ctrl+Shift+P` →「任务: 运行任务」：

- **jiami: 环境检查**：检查虚拟环境和两个已知缺失源文件；缺失时返回非零。
- **jiami: 配置与异常测试**：快速测试四个配置/异常文件；不代表加解密流程通过。
- **jiami: 完整测试（当前缺源码）**：完整 tests 目录；保留真实的失败状态。
- **jiami: Claude 架构方案**：保留的可选脚本入口；当前采用人工交接，不自动运行。
- **jiami: Claude 审查已提交变更**：保留的可选入口；不代表自动交接流程已经完成。

F5 默认可调试配置与异常测试。主程序调试需要先恢复缺失模块。
Python 和 Python Debugger 扩展应安装在 SSH 远端；工作区已声明推荐扩展。

终端对应入口：

```bash
python3 tools/dev.py setup
.venv/bin/python tools/dev.py doctor
.venv/bin/python tools/dev.py test-core
.venv/bin/python tools/dev.py test
.venv/bin/python tools/architect.py plan --question '描述要设计的需求'
git fetch origin
.venv/bin/python tools/architect.py review --base origin/master --ref HEAD --question '描述本次改动和已跑的测试'
```

`setup` 需要 uv，创建 Python 3.12 虚拟环境并同步 `requirements-remote.lock`。
锁文件是远程 CPU/测试环境，不包含 PyQt6、PySide6、CUDA、OpenCL。原 `requirements.txt` 保留桌面依赖。
更新依赖时运行 `python3 tools/dev.py lock`，检查锁文件差异，再运行 setup 和测试。
此锁文件服务于 Linux CPU 环境；Windows GUI 使用独立虚拟环境和原桌面依赖要求。

## 协作流程

1. 你给需求。小修复由 Codex 直接实现；架构、密钥、格式和关键技术变更先请 Claude 设计。
2. Codex 在工作分支实现并执行适当测试，记录通过、失败和未验证项。
3. Codex 提供英文审查问题、固定提交范围和测试证据，由你手动交给 Claude，再将答复贴回。
4. Codex 处理审查意见，必要时针对新提交复审，形成 PR，由你决定合并。

Claude 使用家宽机现有订阅登录。当前 Codex 不自动调用 Claude。若你主动选择保留的脚本入口，审查命令启用 safe mode、restricted 和仅 Read/Glob/Grep 工具，
不加载项目 hooks/插件/MCP，不授予 Bash 或写入工具；由包装脚本保存报告到 `docs/reviews/`。
这是工具权限限制，不是额外的操作系统隔离。不要将凭据或真实私密待加密数据提交进 Git 快照。
失败或超时不表示审查通过，命令返回非零；应先看错误再决定是否重试。

## 已知基线

2026-09-22，原始提交 `bcfbce5`：

- Python 3.12 的 CPU 依赖可以安装，依赖一致性检查通过。
- 配置/异常测试子集 `tools/dev.py test-core`：40 passed。
- 完整 `pytest tests` 在收集阶段因缺失 `src/encryptor/key_injector.py` 和
  `src/decryptor/base_decryptor.py` 失败；`main.py --help` 也因前者失败。
- 该基线阶段用户决定先完成开发底座。当前已确认的后续安全重构范围见 [安全重构决策](security-redesign.md)，缺失模块仍会据实报告。
- GUI、GPU、Windows 打包和完整加解密均未在本轮验证。

Linux 家宽机承担编辑、测试和审查，不能直接替代 Windows 窗口与本机显卡验收。
需要本机验收时从 GitHub 获取指定提交；保持远程为主工作区，避免同一分支双端同时修改。

## 长任务与断线

普通 VS Code 重连会复用服务器。需要 SSH 断线后持续运行的终端任务，可在远端执行
`tmux new-session -A -s jiami -c ~/projects/jiami-file-encryption`，在会话内启动命令。
`Ctrl+B` 再按 `D` 可退出显示而保留会话；不要在 tmux 内再次 attach。
Claude 审查脚本最多等待 10 分钟，超时返回失败，不创建成功报告。

官方参考：[VS Code Remote SSH](https://code.visualstudio.com/docs/remote/ssh)、
[Codex SSH 连接](https://learn.chatgpt.com/docs/remote-connections)、
[Claude CLI](https://code.claude.com/docs/en/cli-reference)。
