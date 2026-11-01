# v1.1.0 — 机翻补翻 + 词典体检

本次更新让"词典没覆盖的插件"也有兜底：可以一键调用机器翻译补齐，另外加了词典体检工具。

## 新增

### 机翻补翻（可选，默认关闭）
- 在偏好设置里勾选「启用机翻补翻」并填入 API Key；
- 选中插件 → 点「机翻补翻选中插件」，只翻译**词典缺失、且不是中文、也不是非界面文字**的词条；
- 结果直接写回该插件的 CSV 并立即生效；
- 支持任意 **OpenAI 兼容**接口，默认 `https://api.deepseek.com` + `deepseek-chat`；
- 可设置每批条数与单次上限，避免一次发太多。

> 费用很低：30 个插件当前缺口约 430 条，一次补齐不到 1 分钱（按 DeepSeek 价格）。
> Key 以明文存在 Blender 偏好设置里，也可以用环境变量 `USER_TRANSLATE_API_KEY`。

### 词典体检
- 面板里的「词典体检」按钮：一键统计词典份数、行数、有效/异常/重复；
- 命令行工具 `tools/dict_audit.py`：
  ```bash
  python tools/dict_audit.py                    # 只体检
  python tools/dict_audit.py --report report.md # 输出报告
  python tools/dict_audit.py --fix              # 清理异常行（自动备份）
  python tools/dict_audit.py --merged merged.csv# 导出去重合并版
  ```
- 当前实测：194 份词典 / 200,096 行，有效 192,755、异常 4,774（2.4%）、重复 19,272。

### 命中率提升
统计口径与匹配策略改进：

- 大小写不敏感、标点/省略号/冒号归一化；
- 跳过非界面文字（标识符、文件名、格式串、纯数字）；
- 跳过本来就是中文的插件（如 Image Editor Master，251 条全是中文）；
- Blender 自带翻译已覆盖的词条计入覆盖。

**30 个已装插件实测：5101 条提取中 4668 条已覆盖 = 91.5%**（v1.0.0 为 79.2%）。

## 安装

下载 `user_translate_auto-1.1.0.zip` → Blender `编辑 → 偏好设置 → 插件 → 从磁盘安装` → 勾选启用。
覆盖安装即可，词典与设置都会保留。

## 兼容性

- Blender 4.1+（实测 4.5.9 LTS / Windows 11）
- 模块名仍是 `user_translate`，可直接覆盖旧版本
