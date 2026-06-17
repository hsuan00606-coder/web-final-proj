import os
from fastapi import FastAPI, HTTPException, status, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
import pymongo
import requests
import bcrypt
import shutil
import uuid
from bson import ObjectId

app = FastAPI(title="歐趴書局 API Backend")

# ==========================================
# 1. 靜態檔案與檔案上傳目錄控管 (方案 A)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")

if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ==========================================
# 2. 初始化資料庫與微服務容器連線
# ==========================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/obooks_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama-ai:11434")

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client.get_database()
users_collection = db["users"]
books_collection = db["books"]
orders_collection = db["orders"] # 新增：訂單集合

chat_sessions = {}

# ==========================================
# 3. Pydantic 資料型態定義 (對齊前端欄位)
# ==========================================
class AuthModel(BaseModel):
    username: str
    password: str
    email: str = None

class ChatRequest(BaseModel):
    session_id: str
    message: str

# ==========================================
# 4. 會員認證 API 路由 (對齊 common.js 的 /auth)
# ==========================================
@app.post("/api/v1/auth/register")
def register(user: AuthModel):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail={"error": "該帳號已被註冊"})
    
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    new_user = {
        "username": user.username,
        "email": user.email,
        "password_hash": hashed_password.decode('utf-8')
    }
    users_collection.insert_one(new_user)
    return {"token": f"bearer-mock-token-{user.username}", "username": user.username}

@app.post("/api/v1/auth/login")
def login(user: AuthModel):
    db_user = users_collection.find_one({"username": user.username})
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=400, detail={"error": "帳號或密碼錯誤"})
    
    return {"token": f"bearer-mock-token-{user.username}", "username": db_user["username"]}

# ==========================================
# 5. 商品 API 路由 (對齊 index.html)
# ==========================================
@app.get("/api/v1/products")
def get_products(q: str = None):
    query = {}
    if q:
        # 模糊搜尋書名
        query["title"] = {"$regex": q, "$options": "i"}
    
    cursor = books_collection.find(query)
    products = []
    for b in cursor:
        products.append({
            "id": str(b["_id"]),
            "name": b["title"],
            "price": b["price"],
            "author": b.get("author", "未知作者"),
            "image": b.get("image_url", "/static/uploads/default.jpg"),
            "rating": b.get("rating", 5)
        })
    return products

# ==========================================
# 6. 訂單核心 API 路由 (對齊 checkout.html 與 orders.html)
# ==========================================
@app.post("/api/v1/orders")
def create_order(order_data: dict):
    order_id = f"AP-{uuid.uuid4().hex[:8].upper()}"
    order_data["orderId"] = order_id
    order_data["date"] = "2026-06-17" # 對齊 Demo 當前時間
    order_data["status"] = "處理中"
    order_data["trackingStage"] = 2  # 1:成立, 2:處理中, 3:配送中, 4:已送達
    order_data["shipping"] = order_data.get("shipping", 60)
    order_data["tax"] = order_data.get("tax", 0)
    order_data["total"] = order_data.get("total", 0)
    
    orders_collection.insert_one(order_data)
    # 去除 MongoDB _id
    order_data.pop("_id", None)
    return {"order": order_data}

@app.get("/api/v1/orders")
def get_all_orders():
    cursor = orders_collection.find({})
    orders = []
    for o in cursor:
        o.pop("_id", None)
        orders.append(o)
    return orders

@app.get("/api/v1/orders/{order_id}")
def get_single_order(order_id: str):
    order = orders_collection.find_one({"orderId": order_id})
    if not order:
        raise HTTPException(status_code=404, detail={"error": "找不到訂單"})
    order.pop("_id", None)
    return order

# ==========================================
# 7. AI Agent 智慧助理 API
# ==========================================
@app.post("/api/v1/chat")
def chat_agent(req: ChatRequest):
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = {"history": []}
    
    session = chat_sessions[req.session_id]
    
    system_prompt = (
        "你現在是台灣中原大學『歐趴書局』的智慧二手教科書助理。 "
        "請全程使用繁體中文回答。請針對使用者的課業問題推薦書籍。"
    )

    try:
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": "llama3.1",
            "prompt": f"{system_prompt}\n\n用戶問題：{req.message}\n助理回答：",
            "stream": False
        }, timeout=30)
        ai_response = response.json().get("response", "AI 助理暫時無法回應")
    except Exception:
        ai_response = f"【測試模式】收到訊息：'{req.message}'。後端通訊正常！"

    session["history"].append({"user": req.message, "ai": ai_response})
    return {"reply": ai_response}

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

# ==========================================
# 8. 從根路徑提供前端頁面 (讓 /index.html、/log_in.html 等導覽連結可用)
#    必須掛載在所有 API 路由之後，API 路由才會優先匹配
# ==========================================
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="root")