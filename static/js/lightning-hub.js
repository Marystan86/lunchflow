import { buildInitDataObject, escapeHtml } from "../utils.js";
import { getDevUserHeader, isDevModeActive } from "./dev-user-switcher.js";

const API_TOKEN_KEY = "meeteat_api_token";
let DEV_MODE = Boolean(window.__DEV_MODE__ === true);
let devModeChecked = false;

let dashboardData = {
  outgoing_requests: [],
  incoming_requests: [],
  group_meetings: [],
  club_events: []
};
let isPublicMode = false;
let canCreateMemberEvent = false;
let canCreateMemberEventReason = "Войдите в приложение";

let selectedIncomingId = null;
let selectedEventCategory = "";

function roundToQuarterHour(date) {
  const rounded = new Date(date);
  rounded.setSeconds(0, 0);
  const minutes = rounded.getMinutes();
  const roundedMinutes = Math.ceil(minutes / 15) * 15;
  if (roundedMinutes >= 60) {
    rounded.setHours(rounded.getHours() + 1);
    rounded.setMinutes(0);
  } else {
    rounded.setMinutes(roundedMinutes);
  }
  return rounded;
}

async function resolveDevMode() {
  if (devModeChecked) return DEV_MODE;
  devModeChecked = true;

  if (window.__DEV_MODE__ === true) {
    DEV_MODE = true;
    console.log("DEV MODE: Telegram bypass enabled");
    return DEV_MODE;
  }

  DEV_MODE = await isDevModeActive();
  if (DEV_MODE) {
    window.__DEV_MODE__ = true;
    console.log("DEV MODE: Telegram bypass enabled");
  }

  return DEV_MODE;
}

async function fetchWithDevHeaders(path, options = {}) {
  const devHeaders = await getDevUserHeader();
  const headers = {
    ...(options.headers || {}),
    ...devHeaders,
  };
  return fetch(path, { ...options, headers, cache: "no-store" });
}

function toDateTimeLocalValue(date) {
  const pad = (num) => String(num).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function getDefaultStartsAtLocalValue() {
  const now = new Date();
  now.setHours(now.getHours() + 2);
  return toDateTimeLocalValue(roundToQuarterHour(now));
}

function updateCreateEventFieldsByFormat() {
  const formatSelect = document.getElementById("eventFormatSelect");
  const citySelect = document.getElementById("eventCitySelect");
  const locationInput = document.getElementById("eventLocationInput");
  const offlineFields = document.getElementById("eventOfflineFields");
  const isOffline = String(formatSelect?.value || "").toLowerCase() === "offline";

  if (offlineFields) offlineFields.classList.toggle("hidden", !isOffline);
  if (citySelect) {
    if (isOffline) {
      citySelect.setAttribute("required", "required");
    } else {
      citySelect.removeAttribute("required");
      citySelect.value = "";
    }
  }
  if (locationInput && !isOffline) {
    locationInput.value = "";
  }
}

function isCreateEventFormValid() {
  const title = String(document.getElementById("eventTitleInput")?.value || "").trim();
  const description = String(document.getElementById("eventDescriptionInput")?.value || "").trim();
  const startsAtRaw = String(document.getElementById("eventStartsAtInput")?.value || "").trim();
  const eventType = String(document.getElementById("eventFormatSelect")?.value || "").trim();
  const city = String(document.getElementById("eventCitySelect")?.value || "").trim();
  const capacity = Number(document.getElementById("eventCapacityInput")?.value || 0);
  const isOffline = eventType === "offline";
  const hasValidDate = Boolean(startsAtRaw) && !Number.isNaN(new Date(startsAtRaw).getTime());
  const baseValid = Boolean(title) && Boolean(description) && hasValidDate && Boolean(eventType) && Number.isFinite(capacity) && capacity >= 2;
  if (!baseValid) return false;
  if (isOffline && !city) return false;
  return true;
}

function updateCreateEventSubmitState() {
  const submitBtn = document.getElementById("createGroupEventSubmitBtn");
  const formatSelect = document.getElementById("eventFormatSelect");
  const citySelect = document.getElementById("eventCitySelect");
  const offlineHint = document.getElementById("eventOfflineHint");
  if (!submitBtn) return;

  const isOffline = String(formatSelect?.value || "").toLowerCase() === "offline";
  const city = String(citySelect?.value || "").trim();
  const formValid = isCreateEventFormValid();

  if (offlineHint) {
    const showHint = isOffline && !city;
    offlineHint.classList.toggle("hidden", !showHint);
  }
  submitBtn.disabled = !formValid;
}

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
  if (await resolveDevMode()) {
    return null;
  }

  const cached = localStorage.getItem(API_TOKEN_KEY);
  if (cached) return cached;

  const initData = getInitDataString();
  if (!initData) throw new Error("Нет данных Telegram для авторизации");

  const response = await fetch("/api/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData })
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Auth failed: ${response.status}${text ? ` ${text}` : ""}`);
  }

  const data = await response.json();
  if (!data?.token) throw new Error("Пустой токен авторизации");

  localStorage.setItem(API_TOKEN_KEY, data.token);
  return data.token;
}

async function apiRequest(path, options = {}) {
  if (await resolveDevMode()) {
    return fetchWithDevHeaders(path, options);
  }

  let token = await ensureApiToken();

  const requestWithToken = async (bearer) => {
    const headers = {
      ...(options.headers || {}),
      Authorization: `Bearer ${bearer}`
    };
    return fetch(path, { ...options, headers, cache: "no-store" });
  };

  let response = await requestWithToken(token);
  if (response.status === 401) {
    localStorage.removeItem(API_TOKEN_KEY);
    token = await ensureApiToken();
    response = await requestWithToken(token);
  }
  return response;
}

function initials(name) {
  return String(name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function linkify(text) {
  const escaped = escapeHtml(String(text || ""));
  return escaped
    .replace(
      /(https?:\/\/[^\s<]+)/g,
      (url) =>
        `<a href="${url}" target="_blank" rel="noopener noreferrer" class="lightning-link">${url}</a>`
    )
    .replace(/\n/g, "<br>");
}

function mapFormat(value, city) {
  const raw = String(value || "").toLowerCase();
  if (raw === "online") return "Онлайн";
  if (raw === "offline") return city ? `Оффлайн (${city})` : "Оффлайн";
  if (!raw) return city ? `Оффлайн (${city})` : "-";
  return value;
}

function mapStatusLabel(status) {
  const s = String(status || "").toLowerCase();
  if (s === "accepted") return "Принято";
  if (s === "declined") return "Отклонено";
  if (s === "cancelled") return "Отменено";
  if (s === "expired") return "Истекло";
  if (s === "completed") return "Завершено";
  if (s === "no_show") return "Неявка";
  if (s === "disputed") return "Спор";
  if (s === "scheduled") return "Запланировано";
  if (s === "confirmed") return "Подтверждено";
  return "Ожидает ответа";
}

function statusClass(status) {
  const s = String(status || "").toLowerCase();
  if (s === "accepted" || s === "completed" || s === "confirmed") return "status-prinyato";
  if (s === "declined" || s === "cancelled" || s === "no_show") return "status-otkloneno";
  if (s === "disputed") return "status-perenos";
  return "status-ozhidaet";
}

function renderListState(list, message, withRetry = false) {
  if (!list) return;
  list.innerHTML = withRetry
    ? `<div class="lightning-empty-state"><p class="lightning-empty-text">${escapeHtml(message)}</p><button id="lightningRetryBtn" class="btn-secondary lightning-retry-btn" type="button">Повторить</button></div>`
    : `<div class="lightning-empty-state"><p class="lightning-empty-text">${escapeHtml(message)}</p></div>`;
}

function combineDateAndTime(dateValue, timeValue) {
  if (!dateValue || !timeValue) return null;
  const value = new Date(`${dateValue}T${timeValue}`);
  if (Number.isNaN(value.getTime())) return null;
  return value;
}

function toDateInputValue(date) {
  return toDateTimeLocalValue(date).slice(0, 10);
}

function toTimeInputValue(date) {
  return toDateTimeLocalValue(date).slice(11, 16);
}

function formatRescheduleSlot(date) {
  const title = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
  const subtitle = new Intl.DateTimeFormat("ru-RU", {
    weekday: "long"
  }).format(date);
  return { title, subtitle: subtitle.charAt(0).toUpperCase() + subtitle.slice(1) };
}

function buildRescheduleSuggestions(baseValue) {
  const parsed = baseValue ? new Date(baseValue) : new Date();
  const baseDate = Number.isNaN(parsed.getTime())
    ? roundToQuarterHour(new Date(Date.now() + 2 * 60 * 60 * 1000))
    : roundToQuarterHour(parsed);
  const suggestionDates = [
    new Date(baseDate.getTime() + 60 * 60 * 1000),
    new Date(baseDate.getTime() + 24 * 60 * 60 * 1000),
    new Date(baseDate.getTime() + 48 * 60 * 60 * 1000),
  ];

  return suggestionDates.map((date) => ({
    value: toDateTimeLocalValue(date),
    ...formatRescheduleSlot(date),
  }));
}

function findIncomingRequestById(requestId) {
  const items = Array.isArray(dashboardData.incoming_requests) ? dashboardData.incoming_requests : [];
  return items.find((item) => Number(item.id) === Number(requestId)) || null;
}

async function resolveIncomingRequestDetails(requestId) {
  const fallback = findIncomingRequestById(requestId);
  if (fallback && Number.isFinite(Number(fallback.from_user_id))) {
    return fallback;
  }

  try {
    const response = await apiRequest("/api/meeting-requests?type=incoming&limit=100", { method: "GET" });
    if (!response.ok) {
      return fallback;
    }
    const body = await response.json().catch(() => ({}));
    const items = Array.isArray(body?.items) ? body.items : [];
    const resolved = items.find((item) => Number(item.id) === Number(requestId));
    if (!resolved) {
      return fallback;
    }

    if (Array.isArray(dashboardData.incoming_requests)) {
      dashboardData.incoming_requests = dashboardData.incoming_requests.map((item) =>
        Number(item.id) === Number(requestId) ? { ...item, ...resolved } : item
      );
    }
    return { ...(fallback || {}), ...resolved };
  } catch (error) {
    console.warn("Failed to resolve incoming request details", error);
    return fallback;
  }
}

function setRescheduleFormValue(date) {
  const dateInput = document.getElementById("rescheduleDate");
  const timeInput = document.getElementById("rescheduleTime");
  if (dateInput) dateInput.value = toDateInputValue(date);
  if (timeInput) timeInput.value = toTimeInputValue(date);
}

function syncRescheduleSuggestionSelection() {
  const dateInput = document.getElementById("rescheduleDate");
  const timeInput = document.getElementById("rescheduleTime");
  const currentValue = combineDateAndTime(dateInput?.value || "", timeInput?.value || "");
  const currentLocal = currentValue ? toDateTimeLocalValue(currentValue) : "";

  document.querySelectorAll(".reschedule-slot").forEach((btn) => {
    const isActive = String(btn.getAttribute("data-datetime") || "") === currentLocal;
    btn.classList.toggle("is-active", isActive);
  });
}

function renderOutgoing() {
  const list = document.getElementById("outgoingRequestsList");
  if (!list) return;

  const items = Array.isArray(dashboardData.outgoing_requests) ? dashboardData.outgoing_requests : [];
  if (!items.length) {
    renderListState(list, "Нет исходящих запросов");
    return;
  }

  list.innerHTML = items
    .map((item) => {
      const format = mapFormat(item.format, item.location);
      const status = mapStatusLabel(item.status);
      const subtitle = "Запрос на встречу 1-на-1";
      return `
        <article class="lightning-card">
          <div class="request-head">
            <div class="request-avatar">${escapeHtml(initials(item.title || "Участник") || "?")}</div>
            <div>
              <p class="request-name">${escapeHtml(item.title || "Участник")}</p>
              <p class="request-title">${escapeHtml(subtitle)}</p>
            </div>
          </div>
          <div class="request-row">
            <span class="request-chip">${escapeHtml(formatDateTime(item.scheduled_for))}</span>
            <span class="request-chip">${escapeHtml(format)}</span>
            <span class="status-badge ${statusClass(item.status)}">${escapeHtml(status)}</span>
          </div>
          <p class="request-note">${escapeHtml(item.message || "")}</p>
        </article>
      `;
    })
    .join("");
}

function renderIncoming() {
  const list = document.getElementById("incomingRequestsList");
  if (!list) return;

  const items = Array.isArray(dashboardData.incoming_requests) ? dashboardData.incoming_requests : [];
  if (!items.length) {
    renderListState(list, "Нет входящих запросов");
    return;
  }

  list.innerHTML = items
    .map((item) => {
      const format = mapFormat(item.format, item.location);
      const status = mapStatusLabel(item.status);
      const isPending = String(item.status || "").toLowerCase() === "pending";
      const subtitle = "Входящий запрос 1-на-1";

      return `
        <article class="lightning-card" data-incoming-id="${item.id}">
          <div class="request-head">
            <div class="request-avatar">${escapeHtml(initials(item.title || "Участник") || "?")}</div>
            <div>
              <p class="request-name">${escapeHtml(item.title || "Участник")}</p>
              <p class="request-title">${escapeHtml(subtitle)}</p>
            </div>
          </div>
          <div class="request-row">
            <span class="request-chip">${escapeHtml(formatDateTime(item.scheduled_for))}</span>
            <span class="request-chip">${escapeHtml(format)}</span>
            <span class="status-badge ${statusClass(item.status)}">${escapeHtml(status)}</span>
          </div>
          <p class="request-note">${escapeHtml(item.message || "")}</p>
          ${isPending && !isPublicMode ? `
            <div class="incoming-actions">
              <div class="incoming-actions-main">
                <button class="btn-primary" data-action="accept" type="button">Принять</button>
                <button class="btn-outline" data-action="reschedule" type="button">Предложить другое время</button>
              </div>
              <button class="btn-text" data-action="decline" type="button">Отклонить</button>
            </div>
          ` : ""}
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest("[data-incoming-id]");
      if (!card) return;
      const requestId = Number(card.getAttribute("data-incoming-id"));
      if (!Number.isFinite(requestId)) return;

      const action = btn.getAttribute("data-action");
      if (action === "reschedule") {
        openRescheduleSheet(requestId);
        return;
      }

      try {
        btn.disabled = true;
        const response = await apiRequest(`/api/lightning/requests/${requestId}/respond`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action })
        });

        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(`HTTP ${response.status}${text ? ` ${text}` : ""}`);
        }

        showToast(action === "accept" ? "Запрос принят" : "Запрос отклонен");
        await loadAndRenderLightning();
      } catch (error) {
        console.error("Failed to respond meeting request", error);
        showToast("Не удалось отправить ответ");
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function renderEvents(listId, items, emptyText) {
  const list = document.getElementById(listId);
  if (!list) return;

  if (!items.length) {
    renderListState(list, emptyText);
    return;
  }

  list.innerHTML = items
    .map((item) => {
      const registered = Number(item.registered || 0);
      const capacity = Number(item.capacity || 0);
      const remaining = Math.max(capacity - registered, 0);
      const format = mapFormat(item.format, item.city);
      const category = item.category ? `<span class="request-chip">${escapeHtml(item.category)}</span>` : "";
      const descriptionHtml = linkify(item.message || "");
      const locationLine = item.location
        ? `<p class="meetup-capacity">Место: ${escapeHtml(String(item.location))}</p>`
        : "";
      const sourceLabel = (() => {
        if (String(item.created_by_role || "").toLowerCase() === "club" || item.is_club_event === true) {
          return "Клуб";
        }
        const byName = String(item.created_by_name || "").trim();
        return byName ? `От участника: ${byName}` : "От участника";
      })();
      const joinDisabled = remaining === 0 || isPublicMode;
      const joinLabel = remaining === 0 ? "Мест нет" : "Записаться";

      return `
        <article class="lightning-card" data-event-id="${item.id}">
          <h3 class="meetup-title">${escapeHtml(item.title || "Событие")}</h3>
          <p class="request-title">${escapeHtml(sourceLabel)}</p>
          <div class="request-row">
            <span class="request-chip">${escapeHtml(formatDateTime(item.scheduled_for))}</span>
            <span class="request-chip">${escapeHtml(format)}</span>
            ${category}
          </div>
          <p class="meetup-desc">${descriptionHtml}</p>
          ${locationLine}
          <p class="meetup-capacity">Зарегистрировано: ${registered} / ${capacity}</p>
          <p class="meetup-capacity">Осталось: ${remaining} мест</p>
          <button class="${joinDisabled ? "btn-secondary" : "btn-primary"} event-cta" data-action="join-event" type="button" ${joinDisabled ? "disabled" : ""}>${joinLabel}</button>
        </article>
      `;
    })
    .join("");

  list.querySelectorAll("button[data-action='join-event']").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest("[data-event-id]");
      if (!card) return;
      const eventId = Number(card.getAttribute("data-event-id"));
      if (!Number.isFinite(eventId)) return;

      try {
        btn.disabled = true;
        const response = await apiRequest(`/api/lightning/events/${eventId}/join`, { method: "POST" });
        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(`HTTP ${response.status}${text ? ` ${text}` : ""}`);
        }
        showToast("Вы записаны на встречу");
        await loadAndRenderLightning();
      } catch (error) {
        console.error("Failed to join event", error);
        showToast("Не удалось записаться");
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function showToast(message) {
  const toast = document.getElementById("lightningToast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.remove("hidden");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.add("hidden"), 2200);
}

function openRescheduleSheet(incomingId) {
  selectedIncomingId = incomingId;
  const sheet = document.getElementById("rescheduleSheet");
  const subtitle = document.getElementById("rescheduleSubtitle");
  const suggestionsList = document.getElementById("rescheduleSuggestions");
  const dateInput = document.getElementById("rescheduleDate");
  const timeInput = document.getElementById("rescheduleTime");
  const noteInput = document.getElementById("rescheduleNote");
  if (!sheet || !suggestionsList || !dateInput || !timeInput || !noteInput) return;

  const incoming = findIncomingRequestById(incomingId);
  const baseDate = incoming?.scheduled_for ? new Date(incoming.scheduled_for) : new Date(Date.now() + 2 * 60 * 60 * 1000);
  const safeDate = Number.isNaN(baseDate.getTime()) ? new Date(Date.now() + 2 * 60 * 60 * 1000) : baseDate;
  const rounded = roundToQuarterHour(safeDate);

  if (subtitle) {
    const name = String(incoming?.title || "участника").trim();
    subtitle.textContent = `Для ${name}`;
  }

  noteInput.value = "";
  setRescheduleFormValue(rounded);
  suggestionsList.innerHTML = buildRescheduleSuggestions(incoming?.scheduled_for).map((option) => `
    <button class="reschedule-slot" type="button" data-datetime="${escapeHtml(option.value)}">
      <span class="reschedule-slot-title">${escapeHtml(option.title)}</span>
      <span class="reschedule-slot-subtitle">${escapeHtml(option.subtitle)}</span>
    </button>
  `).join("");

  suggestionsList.querySelectorAll(".reschedule-slot").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dateTime = btn.getAttribute("data-datetime");
      if (!dateTime) return;
      const value = new Date(dateTime);
      if (Number.isNaN(value.getTime())) return;
      setRescheduleFormValue(value);
      syncRescheduleSuggestionSelection();
    });
  });
  syncRescheduleSuggestionSelection();
  sheet.classList.remove("hidden");
  sheet.setAttribute("aria-hidden", "false");
}

function closeRescheduleSheet() {
  const sheet = document.getElementById("rescheduleSheet");
  const suggestionsList = document.getElementById("rescheduleSuggestions");
  if (!sheet) return;
  if (suggestionsList) suggestionsList.innerHTML = "";
  sheet.classList.add("hidden");
  sheet.setAttribute("aria-hidden", "true");
  selectedIncomingId = null;
}

function openCreateGroupEventModal() {
  const modal = document.getElementById("createGroupEventModal");
  if (!modal) return;

  const titleInput = document.getElementById("eventTitleInput");
  const descriptionInput = document.getElementById("eventDescriptionInput");
  const startsAtInput = document.getElementById("eventStartsAtInput");
  const formatSelect = document.getElementById("eventFormatSelect");
  const citySelect = document.getElementById("eventCitySelect");
  const locationInput = document.getElementById("eventLocationInput");
  const capacityInput = document.getElementById("eventCapacityInput");

  if (titleInput) titleInput.value = "";
  if (descriptionInput) descriptionInput.value = "";
  if (startsAtInput) startsAtInput.value = getDefaultStartsAtLocalValue();
  if (formatSelect) formatSelect.value = "online";
  if (citySelect) citySelect.value = "";
  if (locationInput) locationInput.value = "";
  if (capacityInput) capacityInput.value = "6";
  selectedEventCategory = "";
  document.querySelectorAll(".event-category-chip").forEach((chip) => chip.classList.remove("is-active"));
  updateCreateEventFieldsByFormat();
  updateCreateEventSubmitState();

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

function closeCreateGroupEventModal() {
  const modal = document.getElementById("createGroupEventModal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

async function submitCreateGroupEvent() {
  if (!canCreateMemberEvent) {
    showToast(canCreateMemberEventReason || "Создание недоступно");
    return;
  }
  const title = String(document.getElementById("eventTitleInput")?.value || "").trim();
  const description = String(document.getElementById("eventDescriptionInput")?.value || "").trim();
  const startsAtRaw = String(document.getElementById("eventStartsAtInput")?.value || "").trim();
  const eventType = String(document.getElementById("eventFormatSelect")?.value || "").trim();
  const city = String(document.getElementById("eventCitySelect")?.value || "").trim();
  const location = String(document.getElementById("eventLocationInput")?.value || "").trim();
  const capacity = Number(document.getElementById("eventCapacityInput")?.value || 6);
  const category = selectedEventCategory || null;
  const isOffline = eventType === "offline";

  if (!title || !description || !startsAtRaw || !eventType || !Number.isFinite(capacity) || capacity < 2) {
    showToast("Заполните обязательные поля формы");
    return;
  }
  if (isOffline && !city) {
    showToast("Для оффлайн встречи выберите город");
    return;
  }

  const startsAt = new Date(startsAtRaw);
  if (Number.isNaN(startsAt.getTime())) {
    showToast("Некорректная дата");
    return;
  }

  const payload = {
    title,
    description,
    starts_at: startsAt.toISOString(),
    event_type: eventType,
    city: isOffline ? (city || null) : null,
    location: isOffline ? (location || null) : null,
    capacity: Math.floor(capacity),
    category,
    tags: category ? [category] : [],
  };

  const submitBtn = document.getElementById("createGroupEventSubmitBtn");
  try {
    await resolveDevMode();
    if (submitBtn) submitBtn.disabled = true;
    const response = await apiRequest("/api/events/member", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body?.ok) {
      showToast(body?.detail || "Не удалось создать встречу");
      return;
    }
    closeCreateGroupEventModal();
    showToast("Групповая встреча создана");
    await loadAndRenderLightning();
  } catch (error) {
    console.error("Failed to create group event", error);
    showToast("Ошибка создания встречи");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function refreshCreateButtonPermission() {
  let permission = { can_create_member_event: false, reason: "Войдите в приложение" };
  try {
    const response = await apiRequest("/api/events/permissions", { method: "GET" });
    if (response.ok) {
      permission = await response.json();
    } else {
      const publicResp = await fetchWithDevHeaders("/api/events/permissions", { method: "GET" });
      if (publicResp.ok) permission = await publicResp.json();
    }
  } catch (_) {
    try {
      const publicResp = await fetchWithDevHeaders("/api/events/permissions", { method: "GET" });
      if (publicResp.ok) permission = await publicResp.json();
    } catch {
      permission = { can_create_member_event: false, reason: "Войдите в приложение" };
    }
  }

  canCreateMemberEvent = Boolean(permission?.can_create_member_event);
  canCreateMemberEventReason = String(permission?.reason || "");
  const createBtn = document.getElementById("openCreateGroupEventBtn");
  if (createBtn) {
    createBtn.disabled = !canCreateMemberEvent;
    createBtn.textContent = canCreateMemberEvent ? "Создать групповую встречу" : (canCreateMemberEventReason || "Создание недоступно");
  }
}

function bindRescheduleSheet() {
  const sheet = document.getElementById("rescheduleSheet");
  const backdrop = sheet?.querySelector(".reschedule-backdrop");
  const cancelBtn = document.getElementById("rescheduleCancelBtn");
  const submitBtn = document.getElementById("rescheduleSubmitBtn");
  const dateInput = document.getElementById("rescheduleDate");
  const timeInput = document.getElementById("rescheduleTime");
  const noteInput = document.getElementById("rescheduleNote");

  if (!sheet || !submitBtn || !cancelBtn || !dateInput || !timeInput || !noteInput) return;
  if (sheet.dataset.bound === "1") return;
  sheet.dataset.bound = "1";

  if (backdrop) backdrop.addEventListener("click", closeRescheduleSheet);
  cancelBtn.addEventListener("click", closeRescheduleSheet);
  dateInput.addEventListener("change", syncRescheduleSuggestionSelection);
  timeInput.addEventListener("change", syncRescheduleSuggestionSelection);

  submitBtn.addEventListener("click", async () => {
    const incoming = await resolveIncomingRequestDetails(selectedIncomingId);
    const proposedDate = combineDateAndTime(dateInput.value, timeInput.value);
    const note = noteInput.value.trim();

    if (!selectedIncomingId || !incoming) {
      showToast("Не удалось определить запрос");
      return;
    }
    if (!proposedDate) {
      showToast("Укажите дату и время");
      return;
    }
    if (!Number.isFinite(Number(incoming.from_user_id))) {
      showToast("Не удалось определить участника");
      return;
    }

    let originalDeclined = false;
    try {
      submitBtn.disabled = true;
      cancelBtn.disabled = true;

      const declineResponse = await apiRequest(`/api/lightning/requests/${selectedIncomingId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "decline" })
      });
      const declineBody = await declineResponse.json().catch(() => ({}));
      if (!declineResponse.ok || declineBody?.ok === false) {
        throw new Error(declineBody?.detail || "Не удалось обновить исходный запрос");
      }
      originalDeclined = true;

      const createPayload = {
        to_user_id: Number(incoming.from_user_id),
        scheduled_for: proposedDate.toISOString(),
        format: String(incoming.format || "").toLowerCase() === "offline" ? "offline" : "online",
        location: incoming.location || null,
        message: note || `Предлагаю другое время вместо ${formatDateTime(incoming.scheduled_for)}`
      };

      const createResponse = await apiRequest("/api/lightning/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(createPayload)
      });
      const createBody = await createResponse.json().catch(() => ({}));
      if (!createResponse.ok || createBody?.ok === false) {
        if (createResponse.status === 409) {
          throw new Error("Между участниками уже есть активный запрос");
        }
        if (createResponse.status === 404) {
          throw new Error("Участник не найден");
        }
        throw new Error("Не удалось отправить новый слот");
      }

      closeRescheduleSheet();
      showToast("Новое время отправлено");
      await loadAndRenderLightning();
    } catch (error) {
      console.error("Failed to propose another time", error);
      if (originalDeclined) {
        await loadAndRenderLightning();
        showToast("Исходный запрос закрыт, но новый слот не отправился");
      } else {
        showToast(error instanceof Error && error.message ? error.message : "Не удалось отправить новый слот");
      }
    } finally {
      submitBtn.disabled = false;
      cancelBtn.disabled = false;
    }
  });
}

function bindCreateGroupEventModal() {
  const openBtn = document.getElementById("openCreateGroupEventBtn");
  const modal = document.getElementById("createGroupEventModal");
  const cancelBtn = document.getElementById("createGroupEventCancelBtn");
  const submitBtn = document.getElementById("createGroupEventSubmitBtn");
  const overlay = modal?.querySelector(".reschedule-backdrop");
  if (!modal || !cancelBtn || !submitBtn || !openBtn) return;
  if (modal.dataset.bound === "1") return;
  modal.dataset.bound = "1";

  openBtn.addEventListener("click", openCreateGroupEventModal);
  cancelBtn.addEventListener("click", closeCreateGroupEventModal);
  if (overlay) overlay.addEventListener("click", closeCreateGroupEventModal);
  submitBtn.addEventListener("click", submitCreateGroupEvent);
  document.getElementById("eventFormatSelect")?.addEventListener("change", () => {
    updateCreateEventFieldsByFormat();
    updateCreateEventSubmitState();
  });
  document.getElementById("eventCitySelect")?.addEventListener("change", updateCreateEventSubmitState);
  document.getElementById("eventTitleInput")?.addEventListener("input", updateCreateEventSubmitState);
  document.getElementById("eventDescriptionInput")?.addEventListener("input", updateCreateEventSubmitState);
  document.getElementById("eventStartsAtInput")?.addEventListener("change", updateCreateEventSubmitState);
  document.getElementById("eventCapacityInput")?.addEventListener("input", updateCreateEventSubmitState);
  document.getElementById("eventLocationInput")?.addEventListener("input", updateCreateEventSubmitState);

  document.querySelectorAll(".event-category-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const value = String(chip.getAttribute("data-category") || "").trim();
      const isSame = selectedEventCategory === value;
      selectedEventCategory = isSame ? "" : value;
      document.querySelectorAll(".event-category-chip").forEach((c) => c.classList.remove("is-active"));
      if (!isSame) chip.classList.add("is-active");
      updateCreateEventSubmitState();
    });
  });

  updateCreateEventFieldsByFormat();
  updateCreateEventSubmitState();
}

function renderAllSections() {
  renderOutgoing();
  renderIncoming();
  renderEvents(
    "groupMeetupsList",
    Array.isArray(dashboardData.group_meetings) ? dashboardData.group_meetings : [],
    "Нет групповых встреч"
  );
  renderEvents(
    "clubEventsList",
    Array.isArray(dashboardData.club_events) ? dashboardData.club_events : [],
    "Нет клубных ивентов"
  );
}

async function loadAndRenderLightning() {
  const outgoingList = document.getElementById("outgoingRequestsList");
  const incomingList = document.getElementById("incomingRequestsList");
  const groupList = document.getElementById("groupMeetupsList");
  const clubList = document.getElementById("clubEventsList");

  renderListState(outgoingList, "Загрузка...");
  renderListState(incomingList, "Загрузка...");
  renderListState(groupList, "Загрузка...");
  renderListState(clubList, "Загрузка...");

  try {
    let response;
    try {
      response = await apiRequest("/api/lightning/dashboard?limit=50", { method: "GET" });
      isPublicMode = false;
    } catch (authError) {
      console.warn("Lightning auth failed, fallback to public dashboard:", authError);
      response = await fetchWithDevHeaders("/api/lightning/public/dashboard?limit=50", { method: "GET" });
      isPublicMode = true;
    }

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        response = await fetchWithDevHeaders("/api/lightning/public/dashboard?limit=50", { method: "GET" });
        isPublicMode = true;
      }
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status}${text ? ` ${text}` : ""}`);
      }
    }

    dashboardData = await response.json();
    await refreshCreateButtonPermission();
    renderAllSections();
  } catch (error) {
    console.error("Failed to load lightning dashboard", error);
    renderListState(outgoingList, "Не удалось загрузить данные", true);
    renderListState(incomingList, "Не удалось загрузить данные");
    renderListState(groupList, "Не удалось загрузить данные");
    renderListState(clubList, "Не удалось загрузить данные");
    await refreshCreateButtonPermission();

    const retryBtn = document.getElementById("lightningRetryBtn");
    if (retryBtn) {
      retryBtn.addEventListener("click", () => {
        loadAndRenderLightning();
      }, { once: true });
    }
  }
}

export function sendOnlineInvite(requestId) {
  showToast(`Приглашение отправлено (онлайн): ${requestId}`);
}

export function sendOfflineInvite(requestId) {
  showToast(`Приглашение отправлено (оффлайн): ${requestId}`);
}

export function initLightningHub() {
  if (!document.getElementById("outgoingRequestsList")) return;
  bindRescheduleSheet();
  bindCreateGroupEventModal();
  loadAndRenderLightning();
}



