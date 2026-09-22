# 安全重构决策与实施状态

## 用户已确认的范围

2026-09-22：

1. anti_reverse 只保留有限的文件完整性校验，移除反调试、反虚拟机、分析工具检测及干扰代码。
2. 保留现有 RSA 档位，暂不增加收件人公钥管理或非对称投递功能。
3. 新版本拒绝旧 pickle 文件，迁移工具单独设计；不在正常解密入口提供不安全反序列化开关。
4. 新版本默认不覆盖已有输出。

这些是实施范围。下列状态用于区分已落地和仍待实现的行为。

## 第一阶段：能力描述与完整性模块

- anti_reverse 仅有显式 SHA-256 校验，保留 AntiReverse.check_file_integrity 的兼容名称，
  新入口为 src.security.verify_file_integrity。预期哈希缺失或无效时失败，不允许禁用校验后报告成功。
- 清理 security 包对不存在的 KeyObfuscation／IntegrityCheck 模块的导出。
- 主流程仍使用随机密钥，GUI／出厂配置不再宣称 PBKDF2／Argon2／scrypt 已接入。
  旧的安全配置 key_derivation／anti_reverse_engineering 字段在 JSON Schema 中明确拒绝，
  不将其悄悄解释成已执行的保护。CryptoUtils.derive_key 工具函数保留。
- GUI 自动校验及口令保护暂不可选，以免选择后无效果。
- Claude 由用户手动接入，Codex 提供英文问题、提交范围和验证证据；不自动调用 Claude。

本阶段不改变密文格式，也不承诺现有旧格式安全。

## 第二阶段：协议与恢复链路（待实现）

方向：公开密文包与秘密恢复材料分开；先认证后解密；有边界的数据格式取代 pickle；
共享解密实现生成独立 Python 程序；Windows 可执行文件单独构建验证。

实施前需补齐：

- 覆盖嵌套 RSA／分片元数据的秘密分离规则、秘密包一致性校验和精确认证字节布局。
- 类型标签、分片索引、tuple 操作记录的无歧义序列化。
- 密文／解密器共同发布的故障契约。两次独立重命名不是双文件原子事务。
- 全部 11 个配置档位的支持矩阵；不能只验收最初的五个。

配置清单：basic、standard、high、stealth、paranoid、parallel_fast、blowfish_secure、
salsa20_stream、twofish_strong、multi_algorithm、paranoid_gpu。

四个缺失文件 key_injector.py、base_decryptor.py、cpu_decryptor.py、gpu_decryptor.py
仍未恢复；完整测试与加解密验证仍受阻。测试结果必须区分单元子集、完整 CPU、GPU 真机及 Windows 构建。
