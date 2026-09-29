[CmdletBinding()]
param(
    [switch]$FetchDependencies
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$lock = Get-Content -LiteralPath (Join-Path $repoRoot 'dependencies.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$python = $env:ARK_RECODE_ASSIST_PYTHON
if (-not $python) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $python = $pythonCommand.Source }
} elseif (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command $python -ErrorAction SilentlyContinue
    if ($pythonCommand) { $python = $pythonCommand.Source }
}
if (-not $python -or -not (Test-Path -LiteralPath $python)) {
    throw '请通过 ARK_RECODE_ASSIST_PYTHON 指定 Python 3.12。'
}

$depsRoot = Join-Path $repoRoot '.deps'
$lucimaSource = if ($env:LUCIMA_TOOLS_SOURCE) { $env:LUCIMA_TOOLS_SOURCE } else { Join-Path $depsRoot 'lucima-tools' }
$g8Source = if ($env:G8_PLUGINS_SOURCE) { $env:G8_PLUGINS_SOURCE } else { Join-Path $depsRoot 'g8_plugins' }

function Get-PinnedRepository([string]$Path, [string]$Url, [string]$Commit) {
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) {
        if (-not $FetchDependencies) {
            throw "缺少依赖 $Path；请传入 -FetchDependencies 或设置对应 SOURCE 环境变量。"
        }
        git clone --filter=blob:none $Url $Path
    }
    $actual = (git -c "safe.directory=$($Path.Replace('\','/'))" -C $Path rev-parse HEAD).Trim()
    if ($actual -ne $Commit) {
        if (-not $FetchDependencies) {
            throw "依赖版本不匹配：$Path 当前 $actual，要求 $Commit"
        }
        git -c "safe.directory=$($Path.Replace('\','/'))" -C $Path fetch origin $Commit
        git -c "safe.directory=$($Path.Replace('\','/'))" -C $Path checkout --detach $Commit
    }
}

New-Item -ItemType Directory -Path $depsRoot -Force | Out-Null
Get-PinnedRepository $lucimaSource $lock.dependencies.'lucima-tools'.repository $lock.dependencies.'lucima-tools'.commit
Get-PinnedRepository $g8Source $lock.dependencies.'g8-plugins'.repository $lock.dependencies.'g8-plugins'.commit

$characterData = Join-Path $g8Source 'plugins\g8_gear_analyzer\characters.json'
if (-not (Test-Path -LiteralPath $characterData)) { throw 'g8角色配置文件不存在。' }
$dataTarget = Join-Path $repoRoot 'components\g8-analyzer\src\g8_analyzer\data'
New-Item -ItemType Directory -Path $dataTarget -Force | Out-Null
Copy-Item -LiteralPath $characterData -Destination (Join-Path $dataTarget 'characters.json') -Force

$entry = Join-Path $repoRoot 'components\lucima-bridge\src\ark_recode_bridge\__main__.py'
$dist = Join-Path $repoRoot 'dist'
$work = Join-Path $repoRoot 'build'
& $python -m PyInstaller --noconfirm --clean --onefile --name ark-recode-bridge `
    --distpath $dist --workpath $work --specpath $work `
    --paths (Join-Path $repoRoot 'components\lucima-bridge\src') `
    --paths (Join-Path $repoRoot 'components\g8-analyzer\src') `
    --paths $lucimaSource `
    --add-data "$characterData;g8_analyzer/data" `
    --add-data "$(Join-Path $lucimaSource 'backend\item_names.json');backend" `
    --add-data "$(Join-Path $lucimaSource 'backend\equip_ref.json');backend" `
    --hidden-import backend.config `
    --hidden-import backend.game_client `
    --hidden-import backend.portal `
    --hidden-import backend.token_vault `
    $entry
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败。' }

$pluginBin = Join-Path $repoRoot 'plugins\ark-recode-assist\bin'
New-Item -ItemType Directory -Path $pluginBin -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $dist 'ark-recode-bridge.exe') -Destination (Join-Path $pluginBin 'ark-recode-bridge.exe') -Force

& $python (Join-Path $repoRoot 'scripts\validate-plugin.py')
if ($LASTEXITCODE -ne 0) { throw '插件校验失败。' }
& $python -m unittest discover -s (Join-Path $repoRoot 'tests') -v
if ($LASTEXITCODE -ne 0) { throw '单元测试失败。' }
& $python (Join-Path $repoRoot 'scripts\check-secrets.py')
if ($LASTEXITCODE -ne 0) { throw '隐私扫描失败。' }

$artifacts = Join-Path $repoRoot 'artifacts'
New-Item -ItemType Directory -Path $artifacts -Force | Out-Null
$staging = Join-Path $artifacts 'ark-recode-assist-windows-x64'
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot '.agents') -Destination $staging -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot 'plugins') -Destination $staging -Recurse
Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\install.ps1') -Destination (New-Item -ItemType Directory -Path (Join-Path $staging 'scripts') -Force).FullName
Copy-Item -LiteralPath (Join-Path $repoRoot 'README.md') -Destination $staging
Copy-Item -LiteralPath (Join-Path $repoRoot 'LICENSE-MIT') -Destination $staging
Copy-Item -LiteralPath (Join-Path $repoRoot 'LICENSE-GPL-3.0') -Destination $staging
Copy-Item -LiteralPath (Join-Path $repoRoot 'THIRD_PARTY_NOTICES.md') -Destination $staging

$zip = Join-Path $artifacts 'ark-recode-assist-windows-x64.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  ark-recode-assist-windows-x64.zip" | Set-Content -LiteralPath (Join-Path $artifacts 'SHA256SUMS') -Encoding UTF8
Write-Host "Release 已生成：$zip"
