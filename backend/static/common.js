/* ============================================================
   歐趴書局 - 共用工具 (common.js)
   ============================================================ */
const API = "http://localhost:8000/api/v1";

/* ── 多語系 i18n 工具 ── */
const I18n = {
  _key: "lang",
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
  get: () => localStorage.getItem(I18n._key) || "zh-TW",
  t: (key) => {
    const lang = I18n.get();
    return (I18n.dict[lang] && I18n.dict[lang][key]) || I18n.dict["zh-TW"][key] || key;
  },
  set: (lang) => {
    if (!I18n.dict[lang]) return;
    localStorage.setItem(I18n._key, lang);
    // 重建導覽列並套用頁面翻譯
    const placeholder = document.querySelector(".main-header");
    if (placeholder) placeholder.outerHTML = buildHeader(I18n._lastOptions || {});
    Cart.updateBadge();
    I18n.apply();
  },
  // 套用至帶有 data-i18n / data-i18n-ph 屬性的元素
  apply: () => {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = I18n.t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
      el.placeholder = I18n.t(el.getAttribute("data-i18n-ph"));
    });
  },
};

/* ── Auth 工具 ── */
const Auth = {
  getToken: () => localStorage.getItem("token"),
  getUsername: () => localStorage.getItem("username"),
  isLoggedIn: () => !!localStorage.getItem("token"),
  save: (token, username) => {
    localStorage.setItem("token", token);
    localStorage.setItem("username", username);
  },
  clear: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  },
};

/* ── 購物車工具 ── */
const Cart = {
  _key: "allpass_cart",
  get: () => JSON.parse(localStorage.getItem(Cart._key) || "[]"),
  save: (items) => localStorage.setItem(Cart._key, JSON.stringify(items)),
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
  remove: (productId) => {
    const items = Cart.get().filter((i) => i.productId !== productId);
    Cart.save(items);
    Cart.updateBadge();
  },
  updateQty: (productId, qty) => {
    if (qty <= 0) { Cart.remove(productId); return; }
    const items = Cart.get();
    const item = items.find((i) => i.productId === productId);
    if (item) item.qty = qty;
    Cart.save(items);
    Cart.updateBadge();
  },
  clear: () => { localStorage.removeItem(Cart._key); Cart.updateBadge(); },
  count: () => Cart.get().reduce((s, i) => s + i.qty, 0),
  updateBadge: () => {
    const el = document.getElementById("cart-count");
    if (el) { const c = Cart.count(); el.textContent = c > 0 ? `(${c})` : ""; }
  },
};

/* ── API 請求工具 ── */
async function apiFetch(path, options = {}) {
  const token = Auth.getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = token;
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail?.error || data.error || "請求失敗");
  return data;
}

/* ── Toast 通知 ── */
function showToast(msg, duration = 2000) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), duration);
}

/* ── 星評產生 ── */
function renderStars(rating, max = 5) {
  let html = "";
  for (let i = 1; i <= max; i++) {
    html += i <= rating ? "★" : "☆";
  }
  return `<span class="stars">${html}</span>`;
}

/* ── 導覽列 HTML 產生器 ── */
function buildHeader({ activePage = "", showSearch = false } = {}) {
  I18n._lastOptions = { activePage, showSearch };
  const username = Auth.getUsername();
  const cartCount = Cart.count();
  const cartLabel = I18n.t("nav.cart") + (cartCount > 0 ? ` (${cartCount})` : "");

  const navItems = [
    { id: "nav-login", label: username ? `${username}` : I18n.t("nav.login"), page: "login" },
    { id: "nav-cart", label: cartLabel, page: "cart" },
    { id: "nav-history", label: I18n.t("nav.orders"), page: "orders" },
    { id: "nav-search-order", label: I18n.t("nav.orderQuery"), page: "order_result" },
    { id: "nav-seller", label: I18n.t("nav.seller"), page: "seller" },
  ];

  const navBtns = navItems
    .map((n) => {
      const cls = "btn-pill" + (activePage === n.page ? " active" : "");
      return `<button class="${cls}" id="${n.id}" onclick="navClick('${n.page}')">${n.label}</button>`;
    })
    .join("");

  const searchHtml = showSearch
    ? `<div class="search-container">
        <input type="text" class="search-input" id="search-input" placeholder="${I18n.t("search.placeholder")}" onkeydown="if(event.key==='Enter')doSearch()">
        <button class="search-btn" onclick="doSearch()">🔍</button>
       </div>`
    : "";

  const cur = I18n.get();
  const langs = [
    { code: "zh-TW", label: "繁中" },
    { code: "en", label: "English" },
    { code: "zh-CN", label: "简体" },
  ];
  const langBtns = langs
    .map((l) => `<button class="btn-rect${cur === l.code ? " active" : ""}" onclick="I18n.set('${l.code}')">${l.label}</button>`)
    .join("");

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

/* ── 導覽點擊邏輯 ── */
function navClick(page) {
  // 已登入時點擊會員按鈕 → 登出
  if (page === "login" && Auth.isLoggedIn()) {
    if (confirm(I18n.t("logout"))) {
      Auth.clear();
      location.href = "/index.html";
    }
    return;
  }
  const requireAuth = ["cart", "orders", "order_result", "seller"];
  if (requireAuth.includes(page) && !Auth.isLoggedIn()) {
    showToast("請先登入會員");
    setTimeout(() => (location.href = "/log_in.html"), 1200);
    return;
  }
  const map = {
    login: "/log_in.html",
    cart: "/cart.html",
    orders: "/orders.html",
    order_result: "/order_result.html",
    seller: "/seller.html",
  };
  if (map[page]) location.href = map[page];
}

/* ── 搜尋跳轉 ── */
function doSearch() {
  const input = document.getElementById("search-input");
  if (!input) return;
  const q = input.value.trim();
  location.href = "/index.html" + (q ? `?q=${encodeURIComponent(q)}` : "");
}

/* ── DOM 載入後初始化導覽列 ── */
function initHeader(options = {}) {
  const placeholder = document.getElementById("header-placeholder");
  if (placeholder) {
    placeholder.outerHTML = buildHeader(options);
  }
  Cart.updateBadge();
  I18n.apply();
}
