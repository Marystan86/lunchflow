import { buildInitDataObject, escapeHtml } from "../utils.js";
import { getDevUserHeader, isDevModeActive } from "./dev-user-switcher.js";

const API_TOKEN_KEY = "meeteat_api_token";

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
  const serialized = params.toString();
  return serialized || null;
}

async function ensureApiToken() {
  if (await isDevModeActive()) return null;
  const cached = localStorage.getItem(API_TOKEN_KEY);
  if (cached) return cached;

  const initData = getInitDataString();
  if (!initData) throw new Error("Нет данных Telegram для авторизации");

  const response = await fetch("/api/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData })
  });
  if (!response.ok) throw new Error(`Auth failed: ${response.status}`);

  const data = await response.json();
  if (!data?.token) throw new Error("Пустой токен авторизации");
  localStorage.setItem(API_TOKEN_KEY, data.token);
  return data.token;
}

async function fetchPublicNews() {
  const response = await fetch("/api/news/public?limit=50&offset=0", { cache: "no-store" });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status}${text ? ` ${text}` : ""}`);
  }
  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}

async function fetchNews() {
  if (await isDevModeActive()) {
    const response = await fetch("/api/news?limit=50&offset=0", {
      method: "GET",
      headers: await getDevUserHeader(),
      cache: "no-store"
    });
    if (!response.ok) {
      return fetchPublicNews();
    }
    const payload = await response.json().catch(() => ({}));
    return Array.isArray(payload?.items) ? payload.items : [];
  }

  let token;
  try {
    token = await ensureApiToken();
  } catch (authError) {
    console.warn("News auth failed, fallback to public feed:", authError);
    return fetchPublicNews();
  }

  const requestNews = async (bearer) =>
    fetch("/api/news?limit=50&offset=0", {
      method: "GET",
      headers: { Authorization: `Bearer ${bearer}` },
      cache: "no-store"
    });

  let response = await requestNews(token);
  if (response.status === 401) {
    localStorage.removeItem(API_TOKEN_KEY);
    token = await ensureApiToken();
    response = await requestNews(token);
  }

  if (!response.ok) {
    console.warn("Private news endpoint failed, fallback to public endpoint:", response.status);
    return fetchPublicNews();
  }

  const payload = await response.json();
  return Array.isArray(payload?.items) ? payload.items : [];
}

function defaultTagByType(type) {
  const mapping = {
    admin_post: "Клуб",
    event_announcement: "Ивент",
    event_summary: "Итоги"
  };
  return mapping[String(type || "").toLowerCase()] || "Клуб";
}

function formatNewsDate(isoValue) {
  if (!isoValue) return "";
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long"
  }).format(date);
}

function openLinkedEvent(item) {
  if (String(item.entity_type || "").toLowerCase() !== "event" || !item.entity_id) return;
  const eventId = Number(item.entity_id);
  if (!Number.isFinite(eventId)) return;

  try {
    sessionStorage.setItem("view_event_id", String(eventId));
  } catch (err) {
    console.warn("Cannot persist event id", err);
  }

  window.dispatchEvent(new CustomEvent("open-event-details", { detail: { eventId } }));
  try {
    window.history.pushState({ screen: "feed" }, "", "#feed");
  } catch (err) {
    console.warn("Cannot push feed route", err);
  }
  window.dispatchEvent(new PopStateEvent("popstate", { state: { screen: "feed" } }));
}

function renderFeedCard(item) {
  const card = document.createElement("article");
  card.className = "home-feed-card";

  const tag = String(item.tag || "").trim() || defaultTagByType(item.type);
  const dateLabel = formatNewsDate(item.created_at);
  const hasEventLink = String(item.entity_type || "").toLowerCase() === "event" && item.entity_id !== null;

  card.innerHTML = `
    <div class="home-feed-meta">
      <span class="home-feed-tag">${escapeHtml(tag)}</span>
      <span class="home-feed-date">${escapeHtml(dateLabel)}</span>
    </div>
    <h3 class="home-feed-card-title">${escapeHtml(item.title || "")}</h3>
    <p class="home-feed-description">${escapeHtml(item.body || "")}</p>
    ${hasEventLink ? '<div class="home-feed-footer"><button class="home-feed-action" type="button">Открыть ивент</button></div>' : ""}
  `;

  if (hasEventLink) {
    const btn = card.querySelector(".home-feed-action");
    if (btn) {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openLinkedEvent(item);
      });
    }
  }

  return card;
}

function renderLoading(list) {
  list.innerHTML = '<div class="muted">Загрузка новостей...</div>';
}

function renderEmpty(list) {
  list.innerHTML = '<div class="muted">Пока новостей нет</div>';
}

function renderError(list) {
  list.innerHTML = `
    <div class="muted">
      <div>Не удалось загрузить новости</div>
      <button id="homeFeedRetryBtn" class="btn" type="button">Повторить</button>
    </div>
  `;
}

async function loadAndRenderFeed(list) {
  renderLoading(list);
  try {
    const items = await fetchNews();
    if (!items.length) {
      renderEmpty(list);
      return;
    }
    list.innerHTML = "";
    items.forEach((item) => list.appendChild(renderFeedCard(item)));
  } catch (error) {
    console.error("Failed to load news feed", error);
    renderError(list);
    const retryBtn = document.getElementById("homeFeedRetryBtn");
    if (retryBtn) retryBtn.addEventListener("click", () => loadAndRenderFeed(list), { once: true });
  }
}

export function initHomeFeed() {
  const list = document.getElementById("homeFeedList");
  if (!list) return;
  loadAndRenderFeed(list);
}

