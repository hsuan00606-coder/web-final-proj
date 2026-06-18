@echo off
:: 歐趴書局 - 一鍵自動化部署腳本（首次部署或要重置資料時使用）
chcp 65001 > nul
echo ===================================================
echo   歐趴書局 二手書智慧拍賣網 - 自動化部署指令檔
echo ===================================================

:: 步驟 1：建置映像檔並背景啟動全部四個容器
echo [步驟 1/3] 正在透過 Docker Compose 建置與啟動所有服務容器...
docker-compose up -d --build

:: 步驟 2：等待 MongoDB 就緒後匯入初始資料
echo.
echo [步驟 2/3] 正在等待 MongoDB 伺服器就緒 (預計等待 5 秒)...
timeout /t 5 /nobreak > nul

echo 正在將預設會員帳密與初始商品書籍匯入 MongoDB 資料庫...
:: 將宿主機的 json 複製到 mongodb 容器內，再以 mongoimport 匯入
:: --drop：匯入前先清空集合，避免重複部署造成資料累加
docker cp users_init.json mongodb:/tmp/users_init.json
docker cp books_init.json mongodb:/tmp/books_init.json
docker exec -i mongodb mongoimport --db obooks_db --collection users --drop --file /tmp/users_init.json --jsonArray
docker exec -i mongodb mongoimport --db obooks_db --collection books --drop --file /tmp/books_init.json --jsonArray

:: 步驟 3：載入 / 初始化 Ollama 的 llama3.1 模型（第一次會下載約 4.7GB）
echo.
echo [步驟 3/3] 正在初始化 Ollama AI 大語言模型 (llama3.1)...
echo (如果是第一次下載，大模型約 4.7GB 需要花費數分鐘，請保持網路暢通)
docker exec -it ollama-ai ollama run llama3.1 "你好"

:: 完成提示
echo.
echo ===================================================
echo [SUCCESS] 歐趴書局全容器化環境部屬成功！
echo ===================================================
echo 請打開瀏覽器訪問以下網址進行實機 Demo：
echo http://localhost:8000/static/index.html
echo ===================================================
pause
