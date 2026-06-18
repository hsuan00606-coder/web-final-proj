# ============================================================
#  歐趴書局 - 本機啟動腳本（PowerShell 版，取代 deploy.bat）
#  用法： powershell -ExecutionPolicy Bypass -File deploy.ps1
#  需求：Docker Desktop 已啟動
# ============================================================
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location "D:\used-textbook-system"

Write-Host "==================================================="
Write-Host "  歐趴書局 二手書智慧拍賣網 - 本機啟動"
Write-Host "==================================================="

# 步驟 1：建置並背景啟動所有容器
Write-Host "[步驟 1/3] 建置並啟動所有服務容器..."
docker-compose up -d --build

# 步驟 2：等待 MongoDB 就緒後，「只在資料庫為空時」才匯入初始資料
# （不再用 --drop，註冊的會員、賣家上架的商品與評論都會被當成長期記憶保留）
Write-Host ""
Write-Host "[步驟 2/3] 等待 MongoDB 就緒（5 秒）..."
Start-Sleep -Seconds 5

$userCount = (docker exec mongodb mongosh obooks_db --quiet --eval "db.users.countDocuments()") -as [int]
if ($userCount -gt 0) {
    Write-Host "      已有 $userCount 筆會員資料，保留既有資料庫（不重新匯入）。"
} else {
    Write-Host "      資料庫為空，匯入初始會員與商品資料..."
    docker cp users_init.json mongodb:/tmp/users_init.json
    docker cp books_init.json mongodb:/tmp/books_init.json
    docker exec -i mongodb mongoimport --db obooks_db --collection users --file /tmp/users_init.json --jsonArray
    docker exec -i mongodb mongoimport --db obooks_db --collection books --file /tmp/books_init.json --jsonArray
}

# 步驟 3：載入 / 初始化 Ollama 的 llama3.1 模型（第一次會下載約 4.7GB）
Write-Host ""
Write-Host "[步驟 3/3] 初始化 AI 模型 llama3.1（第一次下載較久）..."
docker exec ollama-ai ollama run llama3.1 "你好"

# 完成
Write-Host ""
Write-Host "==================================================="
Write-Host "[成功] 歐趴書局已啟動！"
Write-Host "  本機網址： http://localhost:8000/static/index.html"
Write-Host "==================================================="
