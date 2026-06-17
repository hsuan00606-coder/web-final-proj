/* ============================================================
   歐趴書局 - 共用工具 (common.js)
   所有頁面都會載入此檔，提供：API 呼叫、登入狀態、購物車、
   多語系、共用導覽列與通知等共用功能。
   ============================================================ */

// 後端 API 的基底路徑。使用「相對路徑」而非寫死 http://localhost:8000，
// 這樣前端不論被部署在本機、區網或外網，都會自動對應到當前網域的後端。
const API = "/api/v1";

/* ── 多語系 i18n 工具 ──
   提供繁中／English／簡體三語切換，語言選擇存於 localStorage。 */
const I18n = {
  _key: "lang",   // localStorage 用來記住語言的鍵名

  // 各語言的字典：key 為翻譯代號，value 為對應字串
  dict: {
    "zh-TW": {
      brand: "歐趴書局",
      "nav.login": "會員登入",
      "nav.cart": "購物車",
      "nav.orders": "歷史訂單",
      "nav.orderQuery": "訂單查詢",
      "nav.seller": "賣家專區",
      "search.placeholder": "關鍵字搜尋框",
      "ai.title": "🤖 AI Agent 智慧課業助理",
      "ai.welcome": "你好！我是中原大學歐趴書局助理。想找什麼必修科目的二手教科書嗎？",
      "ai.inputPlaceholder": "對話搜尋，如：我想找Linux...",
      "ai.send": "發送",
      "ai.thinking": "思考中...",
      logout: "確定要登出嗎？",
    },
    "en": {
      brand: "O-Pass Bookstore",
      "nav.login": "Login",
      "nav.cart": "Cart",
      "nav.orders": "Orders",
      "nav.orderQuery": "Track Order",
      "nav.seller": "Seller Center",
      "search.placeholder": "Search keywords",
      "ai.title": "🤖 AI Study Assistant",
      "ai.welcome": "Hi! I'm the O-Pass Bookstore assistant. Which course textbooks are you looking for?",
      "ai.inputPlaceholder": "Chat to search, e.g. I'm looking for Linux...",
      "ai.send": "Send",
      "ai.thinking": "Thinking...",
      logout: "Are you sure you want to log out?",
    },
    "zh-CN": {
      brand: "欧趴书局",
      "nav.login": "会员登录",
      "nav.cart": "购物车",
      "nav.orders": "历史订单",
      "nav.orderQuery": "订单查询",
      "nav.seller": "卖家专区",
      "search.placeholder": "关键字搜索框",
      "ai.title": "🤖 AI 智能课业助理",
      "ai.welcome": "你好！我是中原大学欧趴书局助理。想找什么必修科目的二手教科书吗？",
      "ai.inputPlaceholder": "对话搜索，如：我想找Linux...",
      "ai.send": "发送",
      "ai.thinking": "思考中...",
      logout: "确定要登出吗？",
    },
  },

  // 取得目前語言；沒設定過則預設繁中
  get: () => localStorage.getItem(I18n._key) || "zh-TW",

  // 翻譯：依目前語言取字串，找不到時退回繁中，再找不到就回傳 key 本身
  t: (key) => {
    const lang = I18n.get();
    return (I18n.dict[lang] && I18n.dict[lang][key]) || I18n.dict["zh-TW"][key] || key;
  },

  // 切換語言：儲存選擇 → 重建導覽列 → 重新套用頁面翻譯
  set: (lang) => {
    if (!I18n.dict[lang]) return;            // 不支援的語言代碼則忽略
    localStorage.setItem(I18n._key, lang);
    // 用上次的設定重建導覽列（導覽列文字依語言而變）
    const placeholder = document.querySelector(".main-header");
    if (placeholder) placeholder.outerHTML = buildHeader(I18n._lastOptions || {});
    Cart.updateBadge();
    I18n.apply();
  },

  // 套用翻譯到 HTML：data-i18n 設定 textContent；data-i18n-ph 設定 placeholder
  apply: () => {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = I18n.t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = I18n.t(el.getAttribute("data-i18n-ph"));
    });
  },
};

/* ── Auth 工具 ──
   以 localStorage 保存登入後的 token 與使用者名稱。 */
const Auth = {
  getToken: () => localStorage.getItem("token"),
  getUsername: () => localStorage.getItem("username"),
  isLoggedIn: () => !!localStorage.getItem("token"),   // 有 token 即視為已登入
  save: (token, username) => {                          // 登入／註冊成功後呼叫
    localStorage.setItem("token", token);
    localStorage.setItem("username", username);
  },
  clear: () => {                                        // 登出時清除
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  },
};

/* ── 購物車工具 ──
   購物車資料存在 localStorage，純前端管理（不經後端）。 */
const Cart = {
  _key: "allpass_cart",
  // 讀取購物車陣列；沒有資料時回空陣列
  get: () => JSON.parse(localStorage.getItem(Cart._key) || "[]"),
  // 寫回購物車陣列
  save: (items) => localStorage.setItem(Cart._key, JSON.stringify(items)),

  // 加入商品：已存在則累加數量，否則新增一筆
  add: (product, qty = 1) => {
    const items = Cart.get();
    const existing = items.find((i) => i.productId === product.id);
    if (existing) {
      existing.qty += qty;
    } else {
      items.push({
        productId: product.id,
        name: product.name,
        price: product.price,
        image: product.image,
        qty,
      });
    }
    Cart.save(items);
    Cart.updateBadge();
  },

  // 移除某商品
  remove: (productId) => {
    const items = Cart.get().filter((i) => i.productId !== productId);
    Cart.save(items);
    Cart.updateBadge();
  },

  // 更新數量；數量歸零或更少則直接移除
  updateQty: (productId, qty) => {
    if (qty <= 0) { Cart.remove(productId); return; }
    const items = Cart.get();
    const item = items.find((i) => i.productId === productId);
    if (item) item.qty = qty;
    Cart.save(items);
    Cart.updateBadge();
  },

  clear: () => { localStorage.removeItem(Cart._key); Cart.updateBadge(); },

  // 計算購物車內商品總件數
  count: () => Cart.get().reduce((s, i) => s + i.qty, 0),

  // 更新導覽列上的購物車數量標記
  updateBadge: () => {
    const el = document.getElementById("cart-count");
    if (el) { const c = Cart.count(); el.textContent = c > 0 ? `(${c})` : ""; }
  },
};

/* ── API 請求工具 ──
   統一處理 fetch：自動帶上 token、解析 JSON、統一錯誤拋出。 */
async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = token;          // 已登入則附帶授權標頭
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json();
  // 後端錯誤格式為 {detail:{error}}，相容舊格式 {error}，皆無則給通用訊息
  if (!res.ok) throw new Error(data.detail?.error || data.error || "請求失敗");
  return data;
}

/* ── Toast 通知 ──
   在畫面上短暫顯示一則訊息（如「已加入購物車」）。 */
function showToast(msg, duration = 2000) {
  let toast = document.getElementById("toast");
  if (!toast) {                                  // 頁面沒有 toast 容器則動態建立
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._timer);                    // 重設計時器，避免訊息提前消失
  toast._timer = setTimeout(() => toast.classList.remove("show"), duration);
}

/* ── 星評產生 ──
   依分數回傳實心★與空心☆組成的字串。 */
function renderStars(rating, max = 5) {
  let html = "";
  for (let i = 1; i <= max; i++) {
    html += i <= rating ? "★" : "☆";
  }
  return `<span class="stars">${html}</span>`;
}

/* ── 導覽列 HTML 產生器 ──
   依登入狀態、購物車數量與目前語言，組出整個頁首 HTML 字串。 */
function buildHeader({ activePage = "", showSearch = false } = {}) {
  I18n._lastOptions = { activePage, showSearch };   // 記住設定，供切換語言時重建用
  const username = Auth.getUsername();
  const cartCount = Cart.count();
  const cartLabel = I18n.t("nav.cart") + (cartCount > 0 ? ` (${cartCount})` : "");

  // 導覽按鈕清單；登入後第一顆顯示使用者名稱（點擊可登出）
  const navItems = [
    { id: "nav-login", label: username ? `${username}` : I18n.t("nav.login"), page: "login" },
    { id: "nav-cart", label: cartLabel, page: "cart" },
    { id: "nav-history", label: I18n.t("nav.orders"), page: "orders" },
    { id: "nav-search-order", label: I18n.t("nav.orderQuery"), page: "order_result" },
    { id: "nav-seller", label: I18n.t("nav.seller"), page: "seller" },
  ];

  // 將按鈕清單轉成 HTML；當前頁加上 active 樣式
  const navBtns = navItems
    .map((n) => {
      const cls = "btn-pill" + (activePage === n.page ? " active" : "");
      return `<button class="${cls}" id="${n.id}" onclick="navClick('${n.page}')">${n.label}</button>`;
    })
    .join("");

  // 是否顯示搜尋框（只有首頁需要）
  const searchHtml = showSearch
    ? `<div class="search-container">
        <input type="text" class="search-input" id="search-input" placeholder="${I18n.t("search.placeholder")}" onkeydown="if(event.key==='Enter')doSearch()">
        <button class="search-btn" onclick="doSearch()">🔍</button>
       </div>`
    : "";

  // 語言切換按鈕，標示目前語言為 active
  const cur = I18n.get();
  const langs = [
    { code: "zh-TW", label: "繁中" },
    { code: "en", label: "English" },
    { code: "zh-CN", label: "简体" },
  ];
  const langBtns = langs
    .map((l) => `<button class="btn-rect${cur === l.code ? " active" : ""}" onclick="I18n.set('${l.code}')">${l.label}</button>`)
    .join("");

  // 組出完整頁首
  return `
    <header class="main-header">
      <div class="banner-top">
        <a class="logo-placeholder" href="/index.html">${I18n.t("brand")}</a>
        <button class="btn-circle" onclick="navClick('login')" title="會員">👤</button>
        ${searchHtml}
        <div class="lang-group">
          ${langBtns}
        </div>
      </div>
      <div class="banner-bottom">
        <nav class="user-nav">${navBtns}</nav>
      </div>
    </header>`;
}

/* ── 導覽點擊邏輯 ──
   依按到的項目決定登出、要求登入或跳轉頁面。 */
function navClick(page) {
  // 已登入時點擊「會員」按鈕 → 詢問後登出
  if (page === "login" && Auth.isLoggedIn()) {
    if (confirm(I18n.t("logout"))) {
      Auth.clear();
      location.href = "/index.html";
    }
    return;
  }
  // 這些頁面需登入才能進入；未登入則提示並導去登入頁
  const requireAuth = ["cart", "orders", "order_result", "seller"];
  if (requireAuth.includes(page) && !Auth.isLoggedIn()) {
    showToast("請先登入會員");
    setTimeout(() => (location.href = "/log_in.html"), 1200);
    return;
  }
  // 各項目對應的頁面網址
  const map = {
    login: "/log_in.html",
    cart: "/cart.html",
    orders: "/orders.html",
    order_result: "/order_result.html",
    seller: "/seller.html",
  };
  if (map[page]) location.href = map[page];
}

/* ── 搜尋跳轉 ──
   讀取搜尋框內容，帶著 q 參數導向首頁進行搜尋。 */
function doSearch() {
  const input = document.getElementById("search-input");
  if (!input) return;
  const q = input.value.trim();
  location.href = "/index.html" + (q ? `?q=${encodeURIComponent(q)}` : "");
}

/* ── DOM 載入後初始化導覽列 ──
   各頁面在載入時呼叫，把 #header-placeholder 換成實際導覽列並套用翻譯。 */
function initHeader(options = {}) {
  const placeholder = document.getElementById("header-placeholder");
  if (placeholder) {
    placeholder.outerHTML = buildHeader(options);
  }
  Cart.updateBadge();
  I18n.apply();
}
