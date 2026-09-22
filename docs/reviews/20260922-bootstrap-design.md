# 首次 Claude 架构建议

基线：`bcfbce5`。本报告为模型建议，并非执行测试后的验收结论。

采纳后的约定以 `docs/architecture.md` 和 `docs/remote-development.md` 为准。
校正：CLI 可以无显示器运行；原答复将 cli/gui 合并描述并不精确。用户已决定本轮只完成开发底座，完整收集不作为本轮通过条件。

# 远程开发工作流建议（架构层面，仅供讨论，未验证部分已标注）

**模块边界**（按仓库现状划分，非新设计）：
- `src/crypto/*`：算法原语层，纯计算，无I/O，适合家宽机跑单元测试。
- `src/encryptor/`、`src/decryptor/`：流程编排层，当前**已知阻塞**——`key_injector.py`、`base_decryptor.py` 两个源文件缺失（`__init__.py` 引用但物理文件不存在），需等你找回原文件后才能让 `pytest` 完成 collection，这是观察到的事实，不是猜测。
- `gui/`、`cli/`：交互层，PyQt6 依赖GUI线程与本机显示，家宽机无显示器不可跑。
- `src/gpu/`：OpenCL依赖硬件，家宽机无GPU，只能做导入级/降级路径测试（未验证是否已有降级分支）。

**验收边界（观察，非结论）**：
- 家宽机CPU侧适合跑：`tests/unit`、`tests/property`（Hypothesis）、`tests/integration` 中不依赖GUI/GPU的部分、flake8语法检查。
- Windows本机适合验收：PyQt6界面交互、GPU路径（若显卡具备OpenCL）、打包/exe生成相关文档所述功能。这两类验收目前均未实际执行，仅按代码结构推断可行性。

**开发入口建议**：
- Codex在家宽机的常规入口：`python -m pytest tests/unit -v`、`tests/property`；避免直接跑 `tests/integration` 全量（含线程池/大文件用例，2GB内存需关注OOM，未验证阈值）。
- 只读审查命令（架构师用，不改代码）：`git log --oneline -20`、`git diff bcfbce5..HEAD --stat`、`flake8 src/ --select=E9,F63,F7,F82`（仅语法/未定义名，不做风格审查）、`python -m pytest --collect-only` 用于确认模块能否被发现。

**完成标准（本次仅底座配置）**：
1. SSH ProxyJump连通，VS Code Remote能打开家宽机工作区；
2. `pytest --collect-only` 不再因缺模块报错（依赖用户找回 `key_injector.py`/`base_decryptor.py`）；
3. `tests/unit` 全绿视为CPU侧基线达标；GUI/GPU验收留待Windows本机单独确认，不在本次范围内。

**明确排除**：本次不做算法安全性/侧信道等全量密码学审计，仅确认工程可运行。
