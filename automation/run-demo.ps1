# 采购前置流程 UI 自动化 PoC 一键演示（仅本地环境）
# 用法（Windows PowerShell / PowerShell 7 均可）：
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\automation\run-demo.ps1
#   pwsh -File .\automation\run-demo.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Step($name) { Write-Host "`n===== $name =====" -ForegroundColor Cyan }
function Run-Node($script) {
    & node $script
    if ($LASTEXITCODE -ne 0) { throw "脚本失败：$script" }
}

Step '0. 加载本地凭据并检查本地环境'
# 优先读取 automation/.env.local（gitignore，格式 KEY=VALUE），其次使用已注入的环境变量
$envFile = Join-Path $PSScriptRoot '.env.local'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
    Write-Host "已加载 $envFile"
}
$required = @('HP_PASSWORD_WANGLUN', 'HP_PASSWORD_JJZR')
$missing = $required | Where-Object { -not [Environment]::GetEnvironmentVariable($_, 'Process') }
if ($missing) { throw "缺少密码环境变量：$($missing -join ', ')。请创建 automation/.env.local 或运行前注入。" }
try {
    $r = Invoke-WebRequest 'http://127.0.0.1/HospitalProcurement/index.html' -UseBasicParsing -TimeoutSec 5
    Write-Host "HP 首页 OK ($($r.StatusCode))"
} catch { throw '本地前端未启动：请先运行 start-local-project.cmd' }
try {
    Invoke-WebRequest 'http://127.0.0.1:17825/health' -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-Host 'hospital-procurement(17825) 健康检查 OK'
} catch { throw 'hospital-procurement(17825) 未启动' }

Step '0b. 同步纪检平台 Redis 登录 key（DB9 -> DB7，本地栈配置差异）'
$oldEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $redisPwd = docker exec hospital-local-stack-redis-1 printenv LOCAL_REDIS_PASSWORD 2>$null
    if (-not $redisPwd) { Write-Warning '未取到 Redis 密码，跳过同步；纪检分配可能 401' }
    else {
        foreach ($u in @('jjzr', 'sjyj')) {
            $val = (docker exec hospital-local-stack-redis-1 redis-cli -a "$redisPwd" --no-auth-warning -n 9 GET $u 2>&1 | Out-String).Trim()
            if ($val -and $val.StartsWith('{')) {
                docker exec hospital-local-stack-redis-1 redis-cli -a "$redisPwd" --no-auth-warning -n 7 SET $u $val EX 172800 2>&1 | Out-Null
                Write-Host "  synced $u"
            } else { Write-Warning "  账号 $u 尚未登录过 registers（DB9 无 key）" }
        }
    }
} finally { $ErrorActionPreference = $oldEap }

Step '1. 采购申请发起（保存草稿 -> 确认）'
Run-Node 'poc/stage1-apply.js'
$s1 = Get-Content 'stage1-result.json' -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $s1.projectName) { throw 'stage1 未产出 projectName' }
$env:APP_NAME = $s1.projectName

Step '2a. 纪检主任分配监督员（接口）'
Run-Node 'poc/stage2a-supervisor.js'
$s2 = Get-Content 'stage2a-result.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$env:REQUEST_CODE = $s2.target.requestCode

Step '2b. 分包-新增子包（UI）'
Run-Node 'poc/stage2b-subpackage.js'

Step '2c. 分包-确认锁定（UI）'
Run-Node 'poc/stage2c-confirm-package.js'

Step '3. 验证结果'
Run-Node 'poc/verify-stage2.js'

Write-Host "`n===== 完成 =====" -ForegroundColor Green
Write-Host "APP_NAME     = $($env:APP_NAME)"
Write-Host "REQUEST_CODE = $($env:REQUEST_CODE)"
Write-Host '截图目录：automation/shots'
Write-Host '结果 JSON：stage1-result.json / stage2a-result.json / stage2b-result.json / stage2c-result.json'
