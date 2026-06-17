import os
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
import pymongo
import chromadb
import requests
import bcrypt

app = FastAPI(title="歐趴書局 API Backend")

# 1. 控管 HTML 前端網頁的核心配置：掛載靜態檔案路由 (方案 A)
# 請確保 backend 目錄下有 static 資料夾
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 2. 初始化外部服務連線
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/obooks_db")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client.get_database()
users_collection = db["users"]
books_collection = db["books"]

# 多輪對話 In-Memory Session 快取字典 (關閉網頁或重啟容器即失效)
chat_sessions = {}

# 3. Pydantic 資料模型定義
class RegisterModel(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

# 4. API 實作
@app.post("/api/register")
def register(user: RegisterModel):
    # 檢查帳號是否存在
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="該 Email 已被註冊")
    
    # 進行安全雜湊加密
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    
    new_user = {
        "email": user.email,
        "password_hash": hashed_password.decode('utf-8'),
        "name": user.name
    }
    users_collection.insert_one(new_user)
    
    # 規格書要求：毫秒級即時跳轉，後端迅速回傳
    return {"status": "success", "message": "註冊成功"}

@app.post("/api/login")
def login(user: LoginModel):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user:
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    
    # 驗證雜湊密碼
    if not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    
    return {"status": "success", "user": {"name": db_user["name"], "email": db_user["email"]}}

@app.post("/api/chat")
def chat_agent(req: ChatRequest):
    # 初始化或還原 Session
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = {"history": [], "last_recommended_ids": []}
    
    session = chat_sessions[req.session_id]
    user_message = req.message
    
    # RAG 工作流模擬（這裡只展示骨架，後續可自行加入 ChromaDB 搜尋與 Llama 3.1 提示詞串接）
    # 範例引導 Llama 3.1 推理：
    try:
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": "llama3.1",
            "prompt": f"你是一位二手教科書智慧助理，請回答用戶問題：{user_message}",
            "stream": False
        }, timeout=30)
        ai_response = response.json().get("response", "AI 暫時無法回應")
    except Exception:
        ai_response = f"【測試模式】收到您的訊息：'{user_message}'。目前 AI 引擎容器正在背景載入中。"

    # 更新記憶
    session["history"].append({"user": user_message, "ai": ai_response})
    
    return {
        "reply": ai_response,
        "last_recommended_ids": session["last_recommended_ids"]
    }

# 首頁重定向導流
@app.get("/")
def read_root():
    return {"message": "歡迎來到歐趴書局後端。請訪問 /static/index.html 進入前端網站。"}