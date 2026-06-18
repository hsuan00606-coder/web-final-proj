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

# 步驟 2：等待 MongoDB 就緒後匯入初始資料
Write-Host ""
Write-Host "[步驟 2/3] 等待 MongoDB 就緒（5 秒）後匯入初始資料..."
Start-Sleep -Seconds 5

# 將初始 json 複製進容器並匯入；--drop 會先清空集合避免重複
docker cp users_init.json mongodb:/tmp/users_init.json
docker cp books_init.json mongodb:/tmp/books_init.json
docker exec -i mongodb mongoimport --db obooks_db --collection users --drop --file /tmp/users_init.json --jsonArray
docker exec -i mongodb mongoimport --db obooks_db --collection books --drop --file /tmp/books_init.json --jsonArray

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
