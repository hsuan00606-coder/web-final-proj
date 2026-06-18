# 後端映像檔：以輕量版 Python 3.10 為基礎
FROM python:3.10-slim

# 設定容器內的工作目錄，後續指令皆在此執行
WORKDIR /app

# 安裝編譯 bcrypt 所需的系統套件（build-essential），並安裝 curl 供健康檢查用；
# 安裝後清除 apt 快取以縮小映像檔體積
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先單獨複製依賴清單並安裝，利用 Docker 層快取（程式碼變動時不必重裝套件）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製後端其餘程式碼進容器
COPY . .

# 對外開放 8000 埠
EXPOSE 8000

# 容器啟動指令：以 uvicorn 執行 FastAPI 應用，監聽所有介面的 8000 埠
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
