[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BridgeArgs
)

$ErrorActionPreference = 'Stop'
$pluginRoot = Split-Path -Parent $PSScriptRoot
$bridge = Join-Path $pluginRoot 'bin\ark-recode-bridge.exe'

if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) {
    throw "未找到 ark-recode-bridge.exe。请重新运行仓库 scripts\install.ps1，或安装最新 Release。"
}

& $bridge @BridgeArgs
exit $LASTEXITCODE
