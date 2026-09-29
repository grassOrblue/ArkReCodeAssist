---
name: ark-recode-assist
description: "仅在用户显式选择或点名星陨助手时，读取本地星陨计划账号快照，分析角色、装备、培养计划，或管理攻略知识。不得隐式调用。"
---

# 星陨助手

本技能只允许显式调用。用户没有选择本插件、没有写 `@星陨助手`，也没有使用
`$ark-recode-assist` 时，不得运行任何脚本、读取账号或访问知识库。

## 安全边界

- 不索取或接收账号密码。
- 只使用 LucimaTools 在当前 Windows 用户下保存的 DPAPI 加密令牌。
- 不输出账号邮箱、访问令牌、刷新令牌、Session 或完整原始快照。
- 当前版本只读。强化、合成、购买、出售等游戏写操作必须明确说明尚未实现。
- 不把本地知识、账号快照或报告提交到 Git。

## 调用桥接程序

从本技能目录解析插件根目录，并调用：

```powershell
powershell -ExecutionPolicy Bypass -File <插件根目录>\scripts\invoke.ps1 -- <参数>
```

不要猜测可执行文件路径，也不要直接运行 LucimaTools 的开发接口。

## 工作流

1. 账号相关请求先运行 `snapshot show`。
2. 如果没有缓存、缓存超过30分钟，或用户明确要求刷新，运行 `snapshot refresh`。
3. 根据请求运行：
   - 总体培养：`analyze account --query "用户需求"`
   - 单角色：`analyze character --name "角色名" --query "用户需求"`
   - 装备：`analyze equipment --limit 20 --query "用户需求"`
4. 使用桥接程序返回的精简JSON回答，不读取完整缓存文件。
5. LucimaTools评分与G8评分必须分别标注，不得合并成一个分数。
6. 资料不足时明确写“资料不足”，不得推测角色配置。

## 知识导入

- 普通导入使用 `knowledge ingest`，默认进入本地知识库。
- 冲突或来源不明确的资料进入待审核状态。
- 只有用户明确要求加入公共知识库时，才先审核，再运行 `knowledge promote`。
- 公开记录必须是简短事实摘要，保留来源链接和许可证信息，不复制整篇攻略或图片。
- 除非用户明确要求提交或推送，否则不要执行 Git 写操作。
