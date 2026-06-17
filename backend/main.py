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
def _serialize_book(b):
    return {
        "id": str(b["_id"]),
        "name": b["title"],
        "price": b["price"],
        "author": b.get("author", "未知作者"),
        "image": b.get("image_url", "/static/uploads/default.jpg"),
        "rating": b.get("rating", 5),
        "description": b.get("description", ""),
        "tags": b.get("tags", []),
    }

# 自然語言常見贅詞，搜尋前先濾除以萃取真正的關鍵字 (如「我想找C語言」→「C語言」)
_SEARCH_FILLERS = [
    "我想找", "我要找", "我想要", "我想買", "我要買", "幫我找", "請幫我找",
    "有沒有", "有無", "請問", "想找", "我要", "推薦", "介紹",
    "相關的", "相關", "方面", "的書", "教科書", "課本", "書籍", "的", "書",
]

def _extract_keyword(q: str) -> str:
    kw = q.strip()
    for f in _SEARCH_FILLERS:
        kw = kw.replace(f, "")
    return kw.strip()

@app.get("/api/v1/products")
def get_products(q: str = None):
    products = [_serialize_book(b) for b in books_collection.find({})]
    if not q:
        return products

    ql = q.lower().strip()
    kw = _extract_keyword(q).lower()

    def matches(p):
        hay = " ".join([
            p["name"], p["author"], p.get("description", ""),
            " ".join(p.get("tags", [])),
        ]).lower()
        # 整句比對 或 萃取關鍵字後比對（支援 AI 對話式查詢）
        if ql and ql in hay:
            return True
        if kw and kw in hay:
            return True
        return False

    return [p for p in products if matches(p)]

@app.get("/api/v1/products/{product_id}")
def get_single_product(product_id: str):
    try:
        book = books_collection.find_one({"_id": ObjectId(product_id)})
    except Exception:
        book = None
    if not book:
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})
    return _serialize_book(book)

def _save_upload(image: UploadFile) -> str:
    ext = os.path.splitext(image.filename)[1] or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        shutil.copyfileobj(image.file, f)
    return f"/static/uploads/{fname}"

@app.post("/api/v1/products")
def create_product(
    title: str = Form(...),
    price: int = Form(...),
    author: str = Form("未知作者"),
    description: str = Form(""),
    tags: str = Form(""),
    seller_email: str = Form(""),
    image: UploadFile = File(None),
):
    image_url = _save_upload(image) if image else "/static/uploads/default.jpg"
    doc = {
        "title": title,
        "price": price,
        "author": author,
        "description": description,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "image_url": image_url,
        "rating": 5,
        "status": "available",
        "seller_email": seller_email,
    }
    res = books_collection.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize_book(doc)

@app.put("/api/v1/products/{product_id}")
def update_product(
    product_id: str,
    title: str = Form(None),
    price: int = Form(None),
    author: str = Form(None),
    description: str = Form(None),
    tags: str = Form(None),
    image: UploadFile = File(None),
):
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})
    if not books_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})

    updates = {}
    if title is not None: updates["title"] = title
    if price is not None: updates["price"] = price
    if author is not None: updates["author"] = author
    if description is not None: updates["description"] = description
    if tags is not None:
        updates["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if image:
        updates["image_url"] = _save_upload(image)

    if updates:
        books_collection.update_one({"_id": oid}, {"$set": updates})
    return _serialize_book(books_collection.find_one({"_id": oid}))

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