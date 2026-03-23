import { buildInitDataObject } from "../utils.js";
import { getDevUserHeader, isDevModeActive } from "./dev-user-switcher.js";

const API_TOKEN_KEY = "meeteat_api_token";

let storeState = {
  points: 0,
  level: "Старт",
  purchases: [],
};

let categories = [{ id: 0, slug: "all", title: "Все" }];
let products = [];
let selectedCategory = "Все";
let pendingProductId = null;

function getInitDataString() {
  const raw = window.Telegram?.WebApp?.initData;
  if (raw && typeof raw === "string" && raw.includes("=")) return raw;

  const obj = buildInitDataObject();
  if (!obj || typeof obj !== "object") return null;

  const params = new URLSearchParams();
  Object.entries(obj).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    params.append(key, String(value));
  });
  return params.toString() || null;
}

async function ensureApiToken() {
  if (await isDevModeActive()) {
    return null;
  }

  const cached = localStorage.getItem(API_TOKEN_KEY);
  if (cached) return cached;

  const initData = getInitDataString();
  if (!initData) throw new Error("Нет данных Telegram для авторизации");

  const response = await fetch("/api/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData }),
  });

  if (!response.ok) throw new Error(`Auth failed: ${response.status}`);
  const data = await response.json();
  if (!data?.token) throw new Error("Пустой токен");

  localStorage.setItem(API_TOKEN_KEY, data.token);
  return data.token;
}

async function apiRequest(path, options = {}) {
  if (await isDevModeActive()) {
    const headers = {
      ...(options.headers || {}),
      ...(await getDevUserHeader()),
    };
    return fetch(path, { ...options, headers, cache: "no-store" });
  }

  let token = await ensureApiToken();
  const run = async (bearer) => {
    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${bearer}`,
    };
    return fetch(path, { ...options, headers, cache: "no-store" });
  };

  let response = await run(token);
  if (response.status === 401) {
    localStorage.removeItem(API_TOKEN_KEY);
    token = await ensureApiToken();
    response = await run(token);
  }
  return response;
}

function showToast(text) {
  const toast = document.getElementById("storeToast");
  if (!toast) return;
  toast.textContent = text;
  toast.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.add("hidden"), 2200);
}

function formatDateTime(dateIso) {
  const dt = new Date(dateIso);
  if (Number.isNaN(dt.getTime())) return "-";
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function categoryByTitle(title) {
  return categories.find((c) => c.title === title) || null;
}

function currentStockText(item) {
  return item.stock_text || "Без ограничений";
}

function getFilteredProducts() {
  if (selectedCategory === "Все") return products;
  return products.filter((p) => p.category === selectedCategory);
}

function renderSummary() {
  const pointsEl = document.getElementById("storePointsValue");
  if (pointsEl) pointsEl.textContent = String(storeState.points ?? 0);
  const levelEl = document.querySelector(".store-level-badge");
  if (levelEl) levelEl.textContent = `Уровень: ${storeState.level || "Старт"}`;
}

function renderCategories() {
  const wrap = document.getElementById("storeCategoryChips");
  if (!wrap) return;

  wrap.innerHTML = categories
    .map((cat) => {
      const activeClass = cat.title === selectedCategory ? "is-active" : "";
      return `<button type="button" class="store-chip ${activeClass}" data-category="${cat.title}">${cat.title}</button>`;
    })
    .join("");

  wrap.querySelectorAll("button[data-category]").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCategory = btn.dataset.category || "Все";
      renderCategories();
      renderItems();
    });
  });
}

function renderItems() {
  const list = document.getElementById("storeItemsList");
  if (!list) return;

  const filtered = getFilteredProducts();
  if (!filtered.length) {
    list.innerHTML = '<p class="store-empty">Товаров пока нет.</p>';
    return;
  }

  list.innerHTML = filtered
    .map((item) => {
      const noPoints = Number(storeState.points || 0) < Number(item.costPoints || 0);
      const stockText = currentStockText(item);
      const notAvailable = /^в наличии:\s*0$/i.test(stockText.toLowerCase());
      const disabled = noPoints || notAvailable;
      let btnText = "Забрать";
      if (notAvailable) btnText = "Нет в наличии";
      else if (noPoints) btnText = "Недостаточно баллов";

      const emojiMap = {
        mentor_oleg_review: "🧠",
        tracker_month: "🗓️",
        tshirt_999: "👕",
        pen_999: "🖊️",
        vip_group_slot: "⭐",
        partner_coffee_discount: "☕",
        closed_event_ticket: "🎟️",
      };
      const icon = emojiMap[item.imageKey] || "🎁";

      return `
        <article class="store-item-card">
          <div class="store-item-head">
            <div class="store-item-image">${icon}</div>
            <div>
              <h3 class="store-item-title">${item.title}</h3>
              <p class="store-item-desc">${item.description || ""}</p>
            </div>
          </div>
          <div class="store-item-meta">
            <span class="store-pill">${item.costPoints} баллов</span>
            <span class="store-pill">${item.category}</span>
            <span class="store-pill">${stockText}</span>
          </div>
          <div class="store-item-actions">
            <button type="button" class="store-btn-primary" data-redeem-id="${item.id}" ${disabled ? "disabled" : ""}>${btnText}</button>
          </div>
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("button[data-redeem-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pendingProductId = Number(btn.dataset.redeemId);
      openConfirmModal();
    });
  });
}

function renderPurchases() {
  const list = document.getElementById("storePurchasesList");
  if (!list) return;

  const rows = Array.isArray(storeState.purchases) ? storeState.purchases : [];
  if (!rows.length) {
    list.innerHTML = '<p class="store-empty">Покупок пока нет.</p>';
    return;
  }

  list.innerHTML = rows
    .map(
      (r) => `
        <article class="store-purchase-row">
          <p class="store-purchase-title">${r.title || "Покупка"}</p>
          <p class="store-purchase-meta">${r.costPoints || 0} баллов • ${formatDateTime(r.redeemedAt)}</p>
          <p class="store-purchase-meta">Статус: ${r.status || "paid"}</p>
        </article>
      `
    )
    .join("");
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

function openConfirmModal() {
  const item = products.find((x) => Number(x.id) === Number(pendingProductId));
  if (!item) return;
  const text = document.getElementById("storeConfirmText");
  if (text) text.textContent = `Списать ${item.costPoints} баллов за "${item.title}"?`;
  openModal("storeConfirmModal");
}

async function redeemPendingItem() {
  const item = products.find((x) => Number(x.id) === Number(pendingProductId));
  if (!item) return;

  try {
    const response = await apiRequest("/api/store/purchase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: Number(item.id), qty: 1 }),
    });

    const payload = await response.json().catch(() => ({}));
    closeModal("storeConfirmModal");

    if (!response.ok) {
      showToast(payload?.detail || "Не удалось оформить покупку");
      return;
    }

    if (payload?.ok === false && payload?.reason === "not_enough_points") {
      showToast("Недостаточно баллов");
      await loadStoreData();
      return;
    }

    if (payload?.already_owned) showToast("Уже куплено ранее");
    else showToast('Готово! Награда добавлена в "Мои покупки".');

    await loadStoreData();
  } catch (error) {
    closeModal("storeConfirmModal");
    console.error("Purchase failed", error);
    showToast("Ошибка покупки");
  }
}

function bindEvents() {
  const confirmCancel = document.getElementById("storeConfirmCancelBtn");
  const confirmSubmit = document.getElementById("storeConfirmSubmitBtn");
  const purchasesOpen = document.getElementById("openPurchasesBtn");
  const purchasesClose = document.getElementById("storePurchasesCloseBtn");
  const confirmOverlay = document.querySelector("#storeConfirmModal .store-modal-overlay");
  const purchasesOverlay = document.querySelector("#storePurchasesModal .store-modal-overlay");

  confirmCancel?.addEventListener("click", () => closeModal("storeConfirmModal"));
  confirmSubmit?.addEventListener("click", redeemPendingItem);
  confirmOverlay?.addEventListener("click", () => closeModal("storeConfirmModal"));

  purchasesOpen?.addEventListener("click", () => {
    renderPurchases();
    openModal("storePurchasesModal");
  });
  purchasesClose?.addEventListener("click", () => closeModal("storePurchasesModal"));
  purchasesOverlay?.addEventListener("click", () => closeModal("storePurchasesModal"));
}

async function loadStoreData() {
  const [categoriesResponse, productsResponse] = await Promise.all([
    fetch("/api/store/categories", { cache: "no-store" }),
    fetch("/api/store/products", { cache: "no-store" }),
  ]);

  let summaryPayload = { points: Number(storeState.points || 120), level: storeState.level || "Активный", purchases: [] };
  try {
    const summaryResponse = await apiRequest("/api/store/summary", { method: "GET" });
    if (summaryResponse.ok) {
      summaryPayload = await summaryResponse.json();
    }
  } catch (error) {
    console.warn("Store summary auth failed, using local fallback summary:", error);
  }

  const categoriesPayload = categoriesResponse.ok ? await categoriesResponse.json() : [];
  const productsPayload = productsResponse.ok ? await productsResponse.json() : [];

  const categoryMap = new Map((Array.isArray(categoriesPayload) ? categoriesPayload : []).map((c) => [c.title, c]));
  categories = [{ id: 0, slug: "all", title: "Все" }, ...(Array.isArray(categoriesPayload) ? categoriesPayload : [])];

  products = (Array.isArray(productsPayload) ? productsPayload : []).map((p) => ({
    id: Number(p.id),
    title: p.title,
    description: p.description,
    costPoints: Number(p.costPoints || 0),
    category: p.category,
    category_slug: p.category_slug,
    stock_text: p.stock_text,
    imageKey: p.imageKey,
    _categoryObj: categoryMap.get(p.category) || null,
  }));

  storeState = {
    points: Number(summaryPayload.points || 0),
    level: summaryPayload.level || "Старт",
    purchases: Array.isArray(summaryPayload.purchases) ? summaryPayload.purchases : [],
  };

  if (!categories.some((c) => c.title === selectedCategory)) selectedCategory = "Все";

  renderSummary();
  renderCategories();
  renderItems();
  renderPurchases();
}

export function initStoreScreen() {
  if (!document.getElementById("storeItemsList")) return;
  pendingProductId = null;
  selectedCategory = "Все";
  bindEvents();
  renderSummary();
  renderCategories();
  renderItems();
  loadStoreData().catch((err) => {
    console.error("Failed to load store", err);
    showToast("Не удалось загрузить магазин");
  });
}

