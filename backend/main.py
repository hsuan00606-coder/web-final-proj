# ============================================================
#  歐趴書局 - 後端主程式 (FastAPI)
#  職責：提供 REST API（會員、商品、訂單、AI 對話）並託管前端靜態頁面
#  執行：uvicorn main:app（見 Dockerfile）
# ============================================================
import os
from fastapi import FastAPI, HTTPException, status, File, Form, UploadFile
from fastapi.staticfiles import StaticFiles      # 用於託管前端 HTML/CSS/JS 與上傳圖片
from pydantic import BaseModel, EmailStr         # 請求資料的型別驗證
import pymongo                                    # MongoDB 連線驅動
import requests                                   # 呼叫 Ollama AI 容器用
import bcrypt                                     # 密碼雜湊（不以明文儲存密碼）
import shutil                                     # 儲存上傳檔案時複製檔案串流
import uuid                                       # 產生唯一訂單編號與圖片檔名
from bson import ObjectId                         # MongoDB 文件主鍵 _id 的型別

# 建立 FastAPI 應用實例（title 會顯示在 /docs 自動文件頁）
app = FastAPI(title="歐趴書局 API Backend")

# ==========================================
# 1. 靜態檔案與檔案上傳目錄控管 (方案 A：前後端同源託管)
# ==========================================
# 以本檔案所在位置為基準推算路徑，確保不論從哪裡啟動都指向正確資料夾
BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # backend/
STATIC_DIR = os.path.join(BASE_DIR, "static")           # backend/static/（前端頁面）
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")        # backend/static/uploads/（商品圖片）

# 首次啟動時若目錄不存在則自動建立，避免掛載或寫檔失敗
if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
if not os.path.exists(UPLOAD_DIR): os.makedirs(UPLOAD_DIR)

# 將 /static 路徑對應到實體資料夾，瀏覽器可直接存取 /static/index.html 等檔案
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ==========================================
# 2. 初始化資料庫與微服務容器連線
# ==========================================
# 連線位址優先讀環境變數（docker-compose 注入），本機開發時退回預設值
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/obooks_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama-ai:11434")

# 建立 MongoDB 連線並取得三個資料集合（collection）
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client.get_database()
users_collection = db["users"]      # 會員帳號
books_collection = db["books"]      # 商品（二手教科書）
orders_collection = db["orders"]    # 訂單

# 以記憶體字典暫存各對話 session 的歷史（重啟後清空，僅供 Demo）
chat_sessions = {}

# ==========================================
# 3. Pydantic 資料型態定義 (對齊前端送出的 JSON 欄位)
# ==========================================
class AuthModel(BaseModel):
    """註冊／登入請求的資料格式。"""
    username: str
    password: str
    email: str = None          # 登入時可省略，僅註冊需要

class ChatRequest(BaseModel):
    """AI 對話請求的資料格式。"""
    session_id: str            # 前端產生的對話識別碼，用來區分不同使用者的歷史
    message: str               # 使用者輸入的訊息

class ReviewModel(BaseModel):
    """商品評論請求的資料格式。"""
    username: str              # 撰寫評論的會員
    rating: int = 5            # 星等 1~5
    text: str                  # 評論內容

# ==========================================
# 4. 會員認證 API 路由 (對齊 common.js 的 /auth)
# ==========================================
@app.post("/api/v1/auth/register")
def register(user: AuthModel):
    """註冊新會員：帳號不可重複，密碼以 bcrypt 雜湊後儲存。"""
    # 帳號唯一性檢查
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail={"error": "該帳號已被註冊"})

    # 將明文密碼加鹽雜湊，資料庫只存雜湊結果
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    new_user = {
        "username": user.username,
        "email": user.email,
        "password_hash": hashed_password.decode('utf-8')
    }
    users_collection.insert_one(new_user)
    # 回傳 mock token（Demo 用，非真正的 JWT 驗證）
    return {"token": f"bearer-mock-token-{user.username}", "username": user.username}

@app.post("/api/v1/auth/login")
def login(user: AuthModel):
    """登入：比對帳號是否存在且密碼雜湊吻合。"""
    db_user = users_collection.find_one({"username": user.username})
    # 帳號不存在 或 密碼不符 → 一律回相同錯誤訊息（避免洩漏帳號是否存在）
    if not db_user or not bcrypt.checkpw(user.password.encode('utf-8'), db_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=400, detail={"error": "帳號或密碼錯誤"})

    return {"token": f"bearer-mock-token-{user.username}", "username": db_user["username"]}

# ==========================================
# 5. 商品 API 路由 (對齊 index.html 與 seller.html)
# ==========================================
def _serialize_book(b):
    """將 MongoDB 的書籍文件轉成前端需要的格式（ObjectId 轉字串、補預設值）。"""
    return {
        "id": str(b["_id"]),                                       # ObjectId 不能直接 JSON 序列化，轉字串
        "name": b["title"],
        "price": b["price"],
        "author": b.get("author", "未知作者"),                     # 用 .get 提供預設值，避免舊資料缺欄位報錯
        "image": b.get("image_url", "/static/uploads/default.jpg"),
        "rating": b.get("rating", 5),
        "description": b.get("description", ""),
        "tags": b.get("tags", []),
        "reviews": b.get("reviews", []),
    }

# 自然語言常見贅詞，搜尋前先濾除以萃取真正的關鍵字 (如「我想找C語言」→「C語言」)
_SEARCH_FILLERS = [
    "我想找", "我要找", "我想要", "我想買", "我要買", "幫我找", "請幫我找",
    "有沒有", "有無", "請問", "想找", "我要", "推薦", "介紹",
    "相關的", "相關", "方面", "的書", "教科書", "課本", "書籍", "的", "書",
]

def _extract_keyword(q: str) -> str:
    """從使用者的整句話中移除贅詞，留下真正要搜尋的關鍵字。"""
    kw = q.strip()
    for f in _SEARCH_FILLERS:
        kw = kw.replace(f, "")
    return kw.strip()

@app.get("/api/v1/products")
def get_products(q: str = None):
    """取得商品列表；帶 q 參數時做關鍵字搜尋（支援 AI 對話式自然語言查詢）。"""
    # 先把所有商品取出並轉成前端格式
    products = [_serialize_book(b) for b in books_collection.find({})]
    if not q:
        return products   # 無搜尋字串 → 回全部

    ql = q.lower().strip()                 # 整句（轉小寫做不分大小寫比對）
    kw = _extract_keyword(q).lower()       # 萃取後的關鍵字

    def matches(p):
        """判斷單一商品是否符合搜尋：比對範圍涵蓋書名、作者、敘述、標籤。"""
        hay = " ".join([
            p["name"], p["author"], p.get("description", ""),
            " ".join(p.get("tags", [])),
        ]).lower()
        # 整句比對 或 萃取關鍵字後比對（兩者其一命中即算符合）
        if ql and ql in hay:
            return True
        if kw and kw in hay:
            return True
        return False

    return [p for p in products if matches(p)]

@app.get("/api/v1/products/{product_id}")
def get_single_product(product_id: str):
    """依商品 id 取得單一商品（供商品詳情頁與賣家編輯表單帶入資料）。"""
    try:
        # 字串 id 轉回 ObjectId；格式錯誤會丟例外，視為找不到
        book = books_collection.find_one({"_id": ObjectId(product_id)})
    except Exception:
        book = None
    if not book:
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})
    return _serialize_book(book)

def _save_upload(image: UploadFile) -> str:
    """將上傳圖片以隨機檔名存進 uploads 目錄，回傳可供前端存取的 URL。"""
    ext = os.path.splitext(image.filename)[1] or ".jpg"   # 沿用原副檔名，沒有就用 .jpg
    fname = f"{uuid.uuid4().hex}{ext}"                     # 隨機檔名避免覆蓋與衝突
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        shutil.copyfileobj(image.file, f)                 # 串流寫入，適合大檔
    return f"/static/uploads/{fname}"

@app.post("/api/v1/products")
def create_product(
    # 以 multipart/form-data 接收（因為含檔案上傳），各欄位用 Form 宣告
    title: str = Form(...),              # ... 代表必填
    price: int = Form(...),
    author: str = Form("未知作者"),
    description: str = Form(""),
    tags: str = Form(""),               # 前端以逗號分隔的字串傳入
    seller_email: str = Form(""),
    image: UploadFile = File(None),     # 圖片可選；未上傳則用預設圖
):
    """賣家新增商品。"""
    image_url = _save_upload(image) if image else "/static/uploads/default.jpg"
    doc = {
        "title": title,
        "price": price,
        "author": author,
        "description": description,
        # 將 "C語言, 程式設計" 這類字串切成陣列並去除空白與空項
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "image_url": image_url,
        "rating": 5,
        "status": "available",
        "seller_email": seller_email,
    }
    res = books_collection.insert_one(doc)
    doc["_id"] = res.inserted_id          # 補上資料庫產生的 _id 再序列化回傳
    return _serialize_book(doc)

@app.put("/api/v1/products/{product_id}")
def update_product(
    product_id: str,
    # 編輯時所有欄位皆可選，未提供的欄位保持原值（預設 None）
    title: str = Form(None),
    price: int = Form(None),
    author: str = Form(None),
    description: str = Form(None),
    tags: str = Form(None),
    image: UploadFile = File(None),
):
    """賣家編輯既有商品；僅更新有送來的欄位。"""
    # 驗證 id 格式與商品存在性
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})
    if not books_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})

    # 動態組合要更新的欄位：只有非 None（有送）的才納入
    updates = {}
    if title is not None: updates["title"] = title
    if price is not None: updates["price"] = price
    if author is not None: updates["author"] = author
    if description is not None: updates["description"] = description
    if tags is not None:
        updates["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if image:                                          # 有上傳新圖才覆蓋
        updates["image_url"] = _save_upload(image)

    if updates:
        books_collection.update_one({"_id": oid}, {"$set": updates})
    # 回傳更新後的最新資料
    return _serialize_book(books_collection.find_one({"_id": oid}))

@app.post("/api/v1/products/{product_id}/reviews")
def add_review(product_id: str, review: ReviewModel):
    """新增商品評論：限「購買過此商品」的會員。"""
    try:
        oid = ObjectId(product_id)
    except Exception:
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})
    if not books_collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail={"error": "找不到商品"})

    # 驗證購買紀錄：該會員須有一筆訂單的商品項目含此 productId
    purchased = orders_collection.find_one({
        "username": review.username,
        "items.productId": product_id,
    })
    if not purchased:
        raise HTTPException(status_code=403, detail={"error": "只有購買過此商品的會員才能撰寫評論"})

    entry = {
        "username": review.username,
        "rating": max(1, min(5, review.rating)),   # 限制在 1~5
        "text": review.text,
        "date": "2026-06-18",
    }
    books_collection.update_one({"_id": oid}, {"$push": {"reviews": entry}})
    book = books_collection.find_one({"_id": oid})
    return {"reviews": book.get("reviews", [])}

# ==========================================
# 6. 訂單核心 API 路由 (對齊 checkout.html 與 orders.html)
# ==========================================
@app.post("/api/v1/orders")
def create_order(order_data: dict):
    """建立訂單：補上訂單編號、日期、狀態等系統欄位後存入資料庫。"""
    # 產生易讀的訂單編號，例如 AP-1A2B3C4D
    order_id = f"AP-{uuid.uuid4().hex[:8].upper()}"
    order_data["orderId"] = order_id
    order_data["date"] = "2026-06-17"   # 對齊 Demo 當前時間
    order_data["status"] = "處理中"
    order_data["trackingStage"] = 2     # 物流階段 1:成立 2:處理中 3:配送中 4:已送達
    # 以下欄位若前端未帶則給預設值
    order_data["shipping"] = order_data.get("shipping", 60)
    order_data["tax"] = order_data.get("tax", 0)
    order_data["total"] = order_data.get("total", 0)

    orders_collection.insert_one(order_data)
    # insert 後 order_data 會被塞入 _id（ObjectId 無法序列化），移除再回傳
    order_data.pop("_id", None)
    return {"order": order_data}

@app.get("/api/v1/orders")
def get_all_orders():
    """取得所有訂單列表（供歷史訂單頁）。"""
    cursor = orders_collection.find({})
    orders = []
    for o in cursor:
        o.pop("_id", None)   # 移除無法序列化的 _id
        orders.append(o)
    return orders

@app.get("/api/v1/orders/{order_id}")
def get_single_order(order_id: str):
    """依訂單編號查詢單一訂單（供訂單查詢頁）。"""
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
    """接收使用者訊息，轉交 Ollama 大語言模型產生回覆並記錄對話歷史。"""
    # 該 session 第一次對話時初始化歷史
    if req.session_id not in chat_sessions:
        chat_sessions[req.session_id] = {"history": []}

    session = chat_sessions[req.session_id]

    # 設定 AI 的角色與語言（system prompt）
    system_prompt = (
        "你現在是台灣中原大學『歐趴書局』的智慧二手教科書助理。 "
        "請全程使用繁體中文回答。請針對使用者的課業問題推薦書籍。"
    )

    try:
        # 呼叫 Ollama 容器的生成 API
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": "llama3.1",
            "prompt": f"{system_prompt}\n\n用戶問題：{req.message}\n助理回答：",
            "stream": False
        }, timeout=30)
        ai_response = response.json().get("response", "AI 助理暫時無法回應")
    except Exception:
        # Ollama 無法連線或逾時 → 退回測試模式，確保前端仍有回應不致中斷
        ai_response = f"【測試模式】收到訊息：'{req.message}'。後端通訊正常！"

    # 紀錄此輪對話
    session["history"].append({"user": req.message, "ai": ai_response})
    return {"reply": ai_response}

# ==========================================
# 8. 首頁導向與根路徑前端託管
# ==========================================
from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    """訪問網站根目錄時自動導向首頁。"""
    return RedirectResponse(url="/static/index.html")

# 從根路徑提供前端頁面 (讓 /index.html、/log_in.html 等導覽連結可用)
# 注意：必須掛載在所有 API 路由「之後」，FastAPI 才會讓 API 路由優先匹配，
#       其餘未匹配的路徑才交給此靜態檔案掛載處理。
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="root")
