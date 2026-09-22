# 安全重构决策与实施状态

## 范围

anti_reverse 仅保留显式 SHA-256 完整性检查。RSA 档位保留，无收件人公钥投递；密钥随机生成，无口令派生/口令保护恢复功能。v1 拒绝旧 pickle，迁移另做。默认不覆盖已有输出。

四个原缺失模块及新格式已经实现，等待按固定提交进行人工代码审查。架构批准、实现完成和安全审计是不同状态。

## 信任与保密边界

`data.jmi` 包含密文和公开的文件名、大小、配置名称、算法及拓扑信息。`recovery.jmis` 和 `recover.py` 含全部恢复秘密，必须保密，不应共享整个包目录。

恢复帧自身携带认证密钥，用于发现损坏、混包及未持有恢复秘密的修改；不能认证整个恢复材料的来源。能替换整个恢复材料与密文的对手可重新生成一套合法包。恢复程序也是代码，必须从可信渠道取得。

默认 CPU 支持全部 11 个出厂档位；GPU、桌面 GUI 和 Windows EXE 需分别验证。保留的配置名称 `paranoid_gpu` 不构成硬件加速承诺。

## 字节布局

整数采用无符号大端编码，版本为 1、flags 为 0，尾部 MAC 为 32 字节 HMAC-SHA256：

```text
JMIS | version:1 | flags:1 | key:32 | header_len:4 | JSON | body_len:8 (=0) | MAC:32
JMI1 | version:1 | flags:1 |          header_len:4 | JSON | body_len:8 | body | MAC:32
```

JMIS 总长度为 `82 + header_len`，JMI1 为 `50 + header_len + body_len`。
恢复帧和数据帧分别用 HKDF-Expand-SHA256 派生 MAC 密钥，info 为 `jiami/v1/secret` 与 `jiami/v1/outer`。MAC 覆盖尾部 MAC 之前全部原始字节，包括恢复帧中的原始密钥及长度字段。

结构检查在认证前；认证在 JSON 解释及密码运算前。JSON 拒绝重复键、非有限数字、超深结构、未知字段和错误类型。头限制 1 MiB、嵌套深度 16、列表元素上限 100000、对象字段上限 10000；整个密文体限制 1 GiB。元数据保留逐层/逐块长度和具体算法变体；私密参数使用明确字段与 base64 字节编码。普通字典不会被解释为任意 Python 对象。

公开/私密帧配对后验证全部算法参数、层编号与拓扑边界，再构造密码运算。恢复 SHA-256 在私密记录中，解密失败或摘要不匹配不得发布明文。RSA 嵌套 AES 参数及线程块的独立密钥也属于私密结构。

文件夹采用 ZIP_STORED 数据归档。先验证全部路径，再写入暂存：拒绝绝对路径、穿越、符号链接、特殊文件、重复/大小写冲突、盘符及文件/目录冲突；限制解包总大小，保留空目录。

## 发布契约

1. 在最终目录的父目录下创建独立 0700 暂存目录，先检查同设备。
2. 各文件以独占新建和私密权限写入，flush、fsync、close。
3. 对暂存密文/恢复材料运行真实读取器的 framing、MAC、结构、配对及计划校验。
4. Linux 自底向上 fsync 暂存目录，再 fsync 父目录保留暂存名称。
5. Linux 通过带类型和 errno 检查的 `renameat2(RENAME_NOREPLACE)` 一次发布目录；Windows 使用同卷 `os.rename`。
6. Linux 再 fsync 最终父目录。此步失败返回「已发布，持久性未确认」，保留已发布结果。

检查同设备只是诊断；重命名可能仍因挂载边界 EXDEV 失败。不支持原子不覆盖、目标已存在或跨卷时，不自动退回覆盖、复制或删除。

发布前失败可保留本次 `.jiami-stage-*` 私密暂存，既有目标不变。并发竞争只有一个最终名称获胜，失败者保留自己的暂存。没有占位最终名称、两文件伪事务、自动接管或续传。发布后的无关清理失败不是发布失败。

明文也先完成验证和暂存，再以不覆盖方式发布。文件夹只有在所有成员恢复完成后才出现最终目录名。

Windows 需要 Python 3.12.4+ 对 0700 目录设置访问控制；不承诺可移植目录 fsync 或断电持久性。Linux 保证取决于支持相应操作且遵守 flush 的本地文件系统/存储硬件。进程终止测试不是物理断电测试。

## 验证要求

全部 11 档覆盖空数据、单字节、整块、非整块、哈希往返及仓库外独立恢复程序。另测真实线程分块、NIST AES-CTR/Twofish 已知答案、错误恢复材料、每字节篡改、嵌套 RSA 秘密变更、旧 pickle 拒绝、路径攻击、现有目标/并发冲突、进程中断和同步失败。

完整入口为 `.venv/bin/python tools/dev.py test`。最终测试记录随 PR/人工交接提供；不把 CPU 回退或适配器模拟测试当作 GPU 证据，不把 Windows 文件发布测试当作 EXE 验收。

参考：[Python mkdir 访问控制](https://docs.python.org/3.12/library/os.html#os.mkdir)、[renameat2](https://man7.org/linux/man-pages/man2/rename.2.html)、[fsync](https://man7.org/linux/man-pages/man2/fsync.2.html)。
