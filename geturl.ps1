# ============================================================
#  歐趴書局 - 輸出當下外網網址（只印一行）
#  用法： powershell -ExecutionPolicy Bypass -File geturl.ps1
#  特性：
#    - 背景維持外網通道（本程式結束後通道仍存活）
#    - 已有可用通道則直接重用（網址不變、不重複開）
#    - 標準輸出只有一行：外網網址
# ============================================================
$ErrorActionPreference = "SilentlyContinue"

$proj = "D:\used-textbook-system"
$key  = "$env:USERPROFILE\.ssh\obooks_tunnel"
$log  = "$env:TEMP\obooks_tunnel.log"

# 從通道輸出檔擷取 https://xxxx.lhr.life 網址
function Get-TunnelUrl {
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9]+\.lhr\.life" | Select-Object -First 1
        if ($m) { return $m.Matches[0].Value }
    }
    return $null
}

# 1) 若已有通道且仍可連線，直接重用並印出網址後結束
$existing = Get-TunnelUrl
if ($existing) {
    try {
        Invoke-WebRequest "$existing/static/index.html" -UseBasicParsing -TimeoutSec 6 | Out-Null
        Write-Output "$existing/static/index.html"
        return
    } catch {}
}

# 2) 確認本機後端有在跑；沒有就啟動容器（需 Docker Desktop 已開）
try {
    Invoke-WebRequest "http://localhost:8000/static/index.html" -UseBasicParsing -TimeoutSec 5 | Out-Null
} catch {
    Push-Location $proj
    docker-compose up -d *> $null
    Pop-Location
    Start-Sleep -Seconds 8
}

# 3) 以隱藏視窗背景啟動 SSH 反向通道（程式結束後仍持續運行）
Remove-Item $log -ErrorAction SilentlyContinue
# ssh 的歡迎訊息寫在 stderr，需一併導向檔案，stdout 才不會混入雜訊（確保只印一行）
Start-Process ssh `
    -ArgumentList @("-i", $key, "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=20",
                    "-R", "80:localhost:8000", "nokey@localhost.run") `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden | Out-Null

# 4) 輪詢取得網址，最後只印出一行
$url = $null
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    $url = Get-TunnelUrl
    if ($url) { break }
}

if ($url) {
    Write-Output "$url/static/index.html"
} else {
    Write-Output "ERROR: cannot get tunnel url (check Docker Desktop and network)"
}
