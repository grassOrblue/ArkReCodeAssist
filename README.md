# 星陨助手（ArkReCodeAssist）

星陨助手是一个仅在用户显式选择时运行的本地 Codex 插件。它读取 LucimaTools 已保存在
Windows 当前用户下的 DPAPI 登录令牌，生成脱敏账号快照，再用 LucimaTools 与 G8 两套规则
分别分析角色、装备和培养优先级。

## 使用边界

- 支持插件入口：`@星陨助手 需求`
- Codex 技能入口：`$ark-recode-assist 需求`
- 未显式选择插件时不会读取账号、访问知识库或启动桥接程序。
- 不要在聊天中发送账号密码。新电脑请先在 LucimaTools 界面登录一次。
- 当前版本完全只读，不提供装备强化、合成、购买或出售功能。

## Windows 安装

### 从 Release 安装

1. 下载 `ark-recode-assist-windows-x64.zip` 并解压。
2. 在 PowerShell 中进入解压目录。
3. 执行 `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1`。
4. 新建聊天后使用 `@星陨助手`。

### 从源码安装

```powershell
git clone https://github.com/grassOrblue/ArkReCodeAssist.git
cd ArkReCodeAssist
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

若源码目录中没有预构建的桥接程序，安装器会尝试下载最新 Release。开发者也可以先运行
`scripts\build-release.ps1`。

## 数据目录

默认数据目录为 `%LOCALAPPDATA%\ArkReCodeAssist\data`。可使用环境变量
`ARK_RECODE_ASSIST_DATA` 覆盖。当前电脑如需沿用原路径，可设置：

```powershell
$env:ARK_RECODE_ASSIST_DATA = 'D:\AllGame\Ark ReCode\g8_data'
```

账号快照、报告、日志和 `settings.local.json` 永远不会提交到 Git。公开、可迁移的攻略摘要
位于 `plugins/ark-recode-assist/knowledge/public/`。

## 开发与测试

```powershell
$python = 'C:\path\to\python.exe'
& $python -m unittest discover -s tests -v
& $python scripts\check-secrets.py
& $python scripts\verify-dependencies.py
```

构建 Windows x64 Release：

```powershell
$env:ARK_RECODE_ASSIST_PYTHON = 'C:\path\to\python.exe'
powershell -ExecutionPolicy Bypass -File .\scripts\build-release.ps1
```

## 许可证

- 插件编排、安装器与 G8 适配层：MIT，见 `LICENSE-MIT`。
- `components/lucima-bridge` 及其构建产物：GPL-3.0-only，见 `LICENSE-GPL-3.0`。
- 第三方来源和固定版本见 `THIRD_PARTY_NOTICES.md` 与 `dependencies.lock.json`。
