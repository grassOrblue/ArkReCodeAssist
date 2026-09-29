[CmdletBinding()]
param(
    [string]$DataRoot,
    [string]$LucimaDataDir,
    [switch]$SkipPluginInstall
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pluginRoot = Join-Path $repoRoot 'plugins\ark-recode-assist'
$bridge = Join-Path $pluginRoot 'bin\ark-recode-bridge.exe'

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw '星陨助手 v0.1.0 仅支持 Windows。'
}

if (-not $DataRoot) {
    if ($env:ARK_RECODE_ASSIST_DATA) {
        $DataRoot = $env:ARK_RECODE_ASSIST_DATA
    } else {
        $DataRoot = Join-Path $env:LOCALAPPDATA 'ArkReCodeAssist\data'
    }
}
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
$env:ARK_RECODE_ASSIST_DATA = $DataRoot
try {
    [Environment]::SetEnvironmentVariable('ARK_RECODE_ASSIST_DATA', $DataRoot, 'User')
} catch {
    Write-Warning '无法写入用户环境变量；将使用本机安装指针定位数据目录。'
}
$installStateDir = Join-Path $env:LOCALAPPDATA 'ArkReCodeAssist'
New-Item -ItemType Directory -Path $installStateDir -Force | Out-Null
@{
    schema_version = 1
    data_root = $DataRoot
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $installStateDir 'install.json') -Encoding UTF8

if (-not $LucimaDataDir) {
    $candidates = @(
        $env:LUCIMA_TOOLS_DATA_DIR,
        (Join-Path (Split-Path $repoRoot -Parent) 'Tool'),
        (Join-Path $env:LOCALAPPDATA 'LucimaTools')
    ) | Where-Object { $_ }
    $LucimaDataDir = $candidates | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'settings.json') -PathType Leaf
    } | Select-Object -First 1
}
if (-not $LucimaDataDir -or -not (Test-Path -LiteralPath (Join-Path $LucimaDataDir 'settings.json'))) {
    throw '未找到 LucimaTools 的 settings.json。请先安装并登录 LucimaTools，再使用 -LucimaDataDir 指定目录。官方项目：https://github.com/StardustChocolate/lucima-tools'
}
$LucimaDataDir = [IO.Path]::GetFullPath($LucimaDataDir)

if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) {
    $temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("ark-recode-assist-" + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    try {
        $zipPath = Join-Path $temporaryRoot 'release.zip'
        $sumsPath = Join-Path $temporaryRoot 'SHA256SUMS'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/grassOrblue/ArkReCodeAssist/releases/latest/download/ark-recode-assist-windows-x64.zip' -OutFile $zipPath
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/grassOrblue/ArkReCodeAssist/releases/latest/download/SHA256SUMS' -OutFile $sumsPath
        $expected = ((Get-Content -LiteralPath $sumsPath -Encoding UTF8 | Select-String 'ark-recode-assist-windows-x64.zip').Line -split '\s+')[0].ToUpperInvariant()
        $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToUpperInvariant()
        if (-not $expected -or $actual -ne $expected) {
            throw 'Release 压缩包 SHA-256 校验失败。'
        }
        $expanded = Join-Path $temporaryRoot 'expanded'
        Expand-Archive -LiteralPath $zipPath -DestinationPath $expanded
        $downloadedBridge = Get-ChildItem -LiteralPath $expanded -Recurse -Filter 'ark-recode-bridge.exe' | Select-Object -First 1
        if (-not $downloadedBridge) {
            throw 'Release 中没有找到 ark-recode-bridge.exe。'
        }
        New-Item -ItemType Directory -Path (Split-Path $bridge -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $downloadedBridge.FullName -Destination $bridge -Force
    } finally {
        $resolvedTemp = [IO.Path]::GetFullPath($temporaryRoot)
        if ($resolvedTemp.StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath()), [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTemp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

$configDir = Join-Path $DataRoot 'config'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$settings = [ordered]@{
    schema_version = 1
    lucima_tools_data_dir = $LucimaDataDir
    repository_root = $repoRoot
    cache_minutes = 30
}
$settings | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $configDir 'settings.local.json') -Encoding UTF8

if (-not $SkipPluginInstall) {
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codex) {
        throw '没有找到 codex 命令。请先安装或更新 Codex，再重新运行安装脚本。'
    }
    & $codex.Source plugin marketplace add $repoRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Warning '插件市场可能已经注册；继续尝试安装插件。'
    }
    & $codex.Source plugin add 'ark-recode-assist@ark-recode-assist-marketplace'
    if ($LASTEXITCODE -ne 0) {
        throw 'Codex 插件安装失败。请运行 codex plugin marketplace list 检查本地市场。'
    }
}

Write-Host "星陨助手安装完成。数据目录：$DataRoot"
Write-Host '请新建聊天后使用 @星陨助手；Codex 技能入口为 $ark-recode-assist。'
