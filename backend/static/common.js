/* ============================================================
   歐趴書局 - 共用工具 (common.js)
   ============================================================ */
const API = "http://localhost:8000/api/v1";

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
  const username = Auth.getUsername();
  const cartCount = Cart.count();
  const cartLabel = cartCount > 0 ? `購物車 (${cartCount})` : "購物車";

  const navItems = [
    { id: "nav-login", label: username ? `${username}` : "會員登入", page: "login" },
    { id: "nav-cart", label: cartLabel, page: "cart" },
    { id: "nav-history", label: "歷史訂單", page: "orders" },
    { id: "nav-search-order", label: "訂單查詢", page: "order_result" },
  ];

  const navBtns = navItems
    .map((n) => {
      const cls = "btn-pill" + (activePage === n.page ? " active" : "");
      return `<button class="${cls}" id="${n.id}" onclick="navClick('${n.page}')">${n.label}</button>`;
    })
    .join("");

  const searchHtml = showSearch
    ? `<div class="search-container">
        <input type="text" class="search-input" id="search-input" placeholder="關鍵字搜尋框" onkeydown="if(event.key==='Enter')doSearch()">
        <button class="search-btn" onclick="doSearch()">🔍</button>
       </div>`
    : "";

  return `
    <header class="main-header">
      <div class="banner-top">
        <a class="logo-placeholder" href="/index.html">歐趴書局</a>
        <button class="btn-circle" onclick="navClick('login')" title="會員">👤</button>
        ${searchHtml}
        <div class="lang-group">
          <button class="btn-rect">英文</button>
          <button class="btn-rect">簡體中文</button>
        </div>
      </div>
      <div class="banner-bottom">
        <nav class="user-nav">${navBtns}</nav>
      </div>
    </header>`;
}

/* ── 導覽點擊邏輯 ── */
function navClick(page) {
  const requireAuth = ["cart", "orders", "order_result"];
  if (requireAuth.includes(page) && !Auth.isLoggedIn()) {
    showToast("請先登入會員");
    setTimeout(() => (location.href = "/log_in.html"), 1200);
    return;
  }
  const map = {
    login: Auth.isLoggedIn() ? null : "/log_in.html",
    cart: "/cart.html",
    orders: "/orders.html",
    order_result: "/order_result.html",
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
}
