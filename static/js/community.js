import { buildInitDataObject, escapeHtml } from "../utils.js";
import { getDevUserHeader, isDevModeActive } from "./dev-user-switcher.js";

const API_TOKEN_KEY = "meeteat_api_token";
const PROFILE_SCREEN = "user_profile_view";
const BADGE_EMOJIS = ["⚡", "🏆", "🤝", "🚀", "💡", "📈"];
const sentInviteMemberIds = new Set();
let latestMembers = [];
let inviteModalState = null;
let inviteModalElement = null;
let inviteToastElement = null;
let DEV_MODE = Boolean(window.__DEV_MODE__ === true);
let devModeChecked = false;

async function resolveDevMode() {
  if (devModeChecked) return DEV_MODE;
  devModeChecked = true;

  if (window.__DEV_MODE__ === true) {
    DEV_MODE = true;
    return DEV_MODE;
  }

  DEV_MODE = await isDevModeActive();
  if (DEV_MODE) window.__DEV_MODE__ = true;

  return DEV_MODE;
}

function getInitDataString() {
  const raw = window.Telegram?.WebApp?.initData;
  if (raw && typeof raw === "string" && raw.includes("=")) {
    return raw;
  }

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
  if (!initData) {
    throw new Error("Нет данных Telegram для авторизации");
  }

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
  const token = data?.token;
  if (!token) throw new Error("Пустой токен авторизации");

  localStorage.setItem(API_TOKEN_KEY, token);
  return token;
}

async function fetchPublicMembers() {
  const response = await fetch("/api/members/public?limit=50&offset=0", { cache: "no-store" });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status}${text ? ` ${text}` : ""}`);
  }
  const payload = await response.json();
  return Array.isArray(payload) ? payload : [];
}

async function fetchMembers() {
  if (await resolveDevMode()) {
    const response = await fetch("/api/members", {
      method: "GET",
      headers: await getDevUserHeader(),
      cache: "no-store",
    });
    if (response.ok) {
      const payload = await response.json().catch(() => []);
      return Array.isArray(payload) ? payload : [];
    }
    return fetchPublicMembers();
  }

  let token;
  try {
    token = await ensureApiToken();
  } catch (authError) {
    console.warn("Telegram auth failed, fallback to public members:", authError);
    return fetchPublicMembers();
  }

  const requestPrivate = async (bearer) =>
    fetch("/api/members", {
      method: "GET",
      headers: { Authorization: `Bearer ${bearer}` },
      cache: "no-store"
    });

  let response = await requestPrivate(token);
  if (response.status === 401) {
    localStorage.removeItem(API_TOKEN_KEY);
    token = await ensureApiToken();
    response = await requestPrivate(token);
  }

  if (!response.ok) {
    console.warn("Private members endpoint failed, fallback to public endpoint");
    return fetchPublicMembers();
  }

  const payload = await response.json();
  return Array.isArray(payload) ? payload : [];
}

async function requestJsonWithOptionalAuth(url, options = {}) {
  const isDevMode = await resolveDevMode();
  const devHeaders = isDevMode ? await getDevUserHeader() : {};
  const baseHeaders = {
    "Content-Type": "application/json",
    ...devHeaders,
    ...(options.headers || {})
  };

  if (isDevMode) {
    return fetch(url, {
      ...options,
      headers: baseHeaders,
      cache: "no-store"
    });
  }

  let token = null;
  try {
    token = await ensureApiToken();
  } catch (_) {
    token = null;
  }

  const fetchWithHeaders = async (headers) =>
    fetch(url, {
      ...options,
      headers,
      cache: "no-store"
    });

  let response;
  if (token) {
    response = await fetchWithHeaders({ ...baseHeaders, Authorization: `Bearer ${token}` });
    if (response.status === 401) {
      localStorage.removeItem(API_TOKEN_KEY);
      token = null;
    }
  }

  if (!response) {
    response = await fetchWithHeaders(baseHeaders);
  }

  return response;
}

async function extractErrorDetail(response) {
  const status = Number(response?.status || 0);
  const statusText = String(response?.statusText || "").trim();
  const contentType = String(response?.headers?.get("content-type") || "").toLowerCase();
  let responseBody = null;

  if (contentType.includes("application/json")) {
    responseBody = await response.json().catch(() => null);
  } else {
    const textBody = await response.text().catch(() => "");
    responseBody = textBody || null;
  }

  let detail = "";
  if (responseBody && typeof responseBody === "object" && "detail" in responseBody && responseBody.detail) {
    detail = String(responseBody.detail);
  } else if (typeof responseBody === "string" && responseBody.trim()) {
    detail = responseBody.trim();
  } else if (statusText) {
    detail = statusText;
  } else {
    detail = `HTTP ${status || "error"}`;
  }

  return { detail, responseBody };
}

function initials(fullName) {
  return String(fullName || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((chunk) => chunk[0]?.toUpperCase() || "")
    .join("");
}

function stripTrailingIndex(value) {
  return String(value || "")
    .replace(/\s*#\d+\b/g, "")
    .trim();
}

function formatRevenue(revenueStr) {
  const raw = stripTrailingIndex(revenueStr);
  if (!raw) return "—";

  const normalized = raw
    .replace(/rub\.?/gi, "")
    .replace(/\brur\b/gi, "")
    .replace(/[₽]/g, "")
    .replace(/\bmln\b/gi, "млн")
    .replace(/\bmillion\b/gi, "млн")
    .replace(/\s{2,}/g, " ")
    .trim();

  if (/[₸]|тг/i.test(normalized)) return normalized;
  if (/млн/i.test(normalized)) {
    return normalized
      .replace(/-/g, "–")
      .replace(/\s+/g, " ")
      .trim()
      .concat(" ₸");
  }
  return normalized;
}

function renderLoading(list) {
  list.innerHTML = '<div class="muted">Загрузка...</div>';
}

function renderEmpty(list) {
  list.innerHTML = `
    <div class="muted">
      <div>Пока нет участников</div>
      <div>Админ добавит мемберов</div>
    </div>
  `;
}

function renderError(list) {
  list.innerHTML = `
    <div class="muted">
      <div>Не удалось загрузить участников</div>
      <button id="communityRetryBtn" class="btn" type="button">Повторить</button>
    </div>
  `;
}

function ensureInviteToast() {
  if (inviteToastElement && document.body.contains(inviteToastElement)) return inviteToastElement;
  const toast = document.createElement("div");
  toast.className = "community-invite-toast hidden";
  toast.setAttribute("aria-live", "polite");
  document.body.appendChild(toast);
  inviteToastElement = toast;
  return toast;
}

function showInviteToast(text) {
  const toast = ensureInviteToast();
  toast.textContent = String(text || "");
  toast.classList.remove("hidden");
  clearTimeout(showInviteToast._timer);
  showInviteToast._timer = setTimeout(() => {
    toast.classList.add("hidden");
  }, 2200);
}

function roundToQuarterHour(date) {
  const d = new Date(date);
  d.setSeconds(0, 0);
  const minutes = d.getMinutes();
  const rounded = Math.ceil(minutes / 15) * 15;
  if (rounded >= 60) {
    d.setHours(d.getHours() + 1, 0, 0, 0);
  } else {
    d.setMinutes(rounded, 0, 0);
  }
  return d;
}

function formatForDatetimeLocal(date) {
  const d = new Date(date);
  const pad = (v) => String(v).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function ensureInviteModal() {
  if (inviteModalElement && document.body.contains(inviteModalElement)) return inviteModalElement;

  const modal = document.createElement("div");
  modal.className = "community-invite-modal hidden";
  modal.innerHTML = `
    <div class="community-invite-overlay" data-close="1"></div>
    <div class="community-invite-panel" role="dialog" aria-modal="true" aria-labelledby="communityInviteTitle">
      <h3 id="communityInviteTitle">Позвать на встречу 1-на-1</h3>
      <p id="communityInviteSubtitle" class="community-invite-sub"></p>
      <label class="community-invite-label">
        <span>Дата и время</span>
        <input id="communityInviteDatetime" type="datetime-local" required />
      </label>
      <label class="community-invite-label">
        <span>Формат</span>
        <select id="communityInviteFormat">
          <option value="online">Онлайн</option>
          <option value="offline">Оффлайн</option>
        </select>
      </label>
      <label class="community-invite-label">
        <span>Комментарий</span>
        <textarea id="communityInviteMessage" rows="3" maxlength="280" placeholder="Коротко опишите цель встречи"></textarea>
      </label>
      <div class="community-invite-actions">
        <button type="button" class="community-btn secondary" data-close="1">Отмена</button>
        <button type="button" class="community-btn" id="communityInviteSubmit">Отправить</button>
      </div>
    </div>
  `;

  modal.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.close === "1") {
      closeInviteModal();
    }
  });

  const submitBtn = modal.querySelector("#communityInviteSubmit");
  if (submitBtn) {
    submitBtn.addEventListener("click", () => submitInviteRequest());
  }

  document.body.appendChild(modal);
  inviteModalElement = modal;
  return modal;
}

function openInviteModal(member) {
  if (!member || !member.id) return;
  const modal = ensureInviteModal();
  const datetimeInput = modal.querySelector("#communityInviteDatetime");
  const messageInput = modal.querySelector("#communityInviteMessage");
  const formatInput = modal.querySelector("#communityInviteFormat");
  const subtitle = modal.querySelector("#communityInviteSubtitle");
  const submitBtn = modal.querySelector("#communityInviteSubmit");
  if (!(datetimeInput instanceof HTMLInputElement)) return;
  if (!(messageInput instanceof HTMLTextAreaElement)) return;
  if (!(formatInput instanceof HTMLSelectElement)) return;
  if (!(subtitle instanceof HTMLElement)) return;
  if (!(submitBtn instanceof HTMLButtonElement)) return;

  const defaultTime = roundToQuarterHour(new Date(Date.now() + 2 * 60 * 60 * 1000));
  datetimeInput.value = formatForDatetimeLocal(defaultTime);
  messageInput.value = "";
  formatInput.value = "online";
  submitBtn.disabled = false;
  submitBtn.textContent = "Отправить";

  inviteModalState = {
    toUserId: Number(member.id),
    memberName: member.full_name || "Участник",
    submitting: false
  };
  subtitle.textContent = `Для ${inviteModalState.memberName}`;
  modal.classList.remove("hidden");
}

function closeInviteModal() {
  if (!inviteModalElement) return;
  inviteModalElement.classList.add("hidden");
  inviteModalState = null;
}

async function submitInviteRequest() {
  if (!inviteModalElement || !inviteModalState || inviteModalState.submitting) return;

  const datetimeInput = inviteModalElement.querySelector("#communityInviteDatetime");
  const messageInput = inviteModalElement.querySelector("#communityInviteMessage");
  const formatInput = inviteModalElement.querySelector("#communityInviteFormat");
  const submitBtn = inviteModalElement.querySelector("#communityInviteSubmit");

  if (!(datetimeInput instanceof HTMLInputElement)) return;
  if (!(messageInput instanceof HTMLTextAreaElement)) return;
  if (!(formatInput instanceof HTMLSelectElement)) return;
  if (!(submitBtn instanceof HTMLButtonElement)) return;

  const dateValue = String(datetimeInput.value || "").trim();
  if (!dateValue) {
    showInviteToast("Укажите дату и время");
    return;
  }

  const proposed = new Date(dateValue);
  if (Number.isNaN(proposed.getTime())) {
    showInviteToast("Некорректная дата");
    return;
  }

  inviteModalState.submitting = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "Отправка...";

  const payload = {
    to_user_id: Number(inviteModalState.toUserId),
    proposed_time: dateValue,
    format: String(formatInput.value || "online"),
    message: String(messageInput.value || "").trim() || null
  };
  const toUserId = Number(inviteModalState.toUserId);

  try {
    const response = await requestJsonWithOptionalAuth("/api/meeting-requests", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const { detail, responseBody } = await extractErrorDetail(response);
      console.error("Failed to create 1:1 request", {
        status: response.status,
        responseBody,
        payload
      });
      throw new Error(detail);
    }

    sentInviteMemberIds.add(toUserId);
    closeInviteModal();
    showInviteToast("Запрос отправлен");

    const card = document.querySelector(`.member-preview-card[data-id="${CSS.escape(String(toUserId))}"]`);
    if (card) {
      const btn = card.querySelector(".mp-invite-btn");
      if (btn instanceof HTMLButtonElement) {
        btn.disabled = true;
        btn.innerHTML = '<span class="mp-invite-label">Запрос отправлен</span>';
      }
    }
  } catch (error) {
    if (!(error instanceof Error)) {
      console.error("Failed to create 1:1 request", { error, payload });
    }
    const detail = error instanceof Error ? error.message : "неизвестная ошибка";
    showInviteToast(`Не удалось отправить запрос: ${detail}`);
    submitBtn.disabled = false;
    submitBtn.textContent = "Отправить";
    if (inviteModalState) inviteModalState.submitting = false;
    return;
  }

  if (inviteModalState) inviteModalState.submitting = false;
}

function openMemberProfile(member) {
  const profileKey = member?.tg_id ?? member?.id;
  if (!profileKey) return;

  try {
    sessionStorage.setItem("view_tg_id", String(profileKey));
  } catch (err) {
    console.warn("Cannot write view_tg_id", err);
  }

  try {
    const previewPayload = {
      id: member?.id ?? null,
      tg_id: member?.tg_id ?? null,
      full_name: member?.full_name ?? null,
      photo_url: member?.photo_url ?? null,
      city: member?.city ?? null,
      company: member?.company ?? member?.company_name ?? null,
      industry: member?.industry ?? null,
      annual_revenue: member?.annual_revenue ?? null,
      employee_count: member?.employee_count ?? null,
      club_request: member?.club_request ?? null,
      help_offer: member?.help_offer ?? null,
      hobbies: member?.hobbies ?? null,
      core_competencies: member?.core_competencies ?? null,
      badges_preview: Array.isArray(member?.badges_preview) ? member.badges_preview : [],
      points_balance: member?.points_balance ?? null,
      one_on_one_meetings_count: member?.one_on_one_meetings_count ?? member?.one_on_one_count ?? null,
      group_events_count: member?.group_events_count ?? member?.group_events ?? null,
    };
    sessionStorage.setItem("view_member_preview", JSON.stringify(previewPayload));
  } catch (err) {
    console.warn("Cannot write view_member_preview", err);
  }

  try {
    window.history.pushState({ screen: PROFILE_SCREEN }, "", `#${PROFILE_SCREEN}`);
  } catch (err) {
    console.warn("Cannot push history state", err);
  }

  window.dispatchEvent(new PopStateEvent("popstate", { state: { screen: PROFILE_SCREEN } }));
}

function normalizeBadge(badge) {
  if (!badge) return null;
  if (typeof badge === "string") {
    const code = String(badge || "").trim();
    if (!code) return null;
    return { code, title: code, badgeType: "system" };
  }

  const code = String(badge.code || "").trim();
  if (!code) return null;
  const badgeType = String(badge.badge_type || "").trim().toLowerCase() === "peer" ? "peer" : "system";

  return {
    code,
    title: String(badge.title || badge.code || "Badge"),
    badgeType
  };
}

function getMiniBadgeEmoji(member, index = 0) {
  const len = BADGE_EMOJIS.length;
  const rawId = Number(member?.id);
  const safeIndex = Number.isFinite(rawId) ? Math.abs(rawId) : Math.abs(Number(index) || 0);
  return BADGE_EMOJIS[safeIndex % len];
}

function renderBadges(member, index = 0) {
  const raw = Array.isArray(member.badges_preview)
    ? member.badges_preview.slice(0, 3).map(normalizeBadge).filter(Boolean)
    : [];
  if (!raw.length) return "";

  const emoji = getMiniBadgeEmoji(member, index);

  return raw
    .map((badge) => {
      const isUsersIconBadge = badge.code === "pleasant_talker";
      if (isUsersIconBadge) {
        return `
        <span class="mp-badge" title="${escapeHtml(badge.title)}">
          <div class="mini-badge-emoji">${escapeHtml(emoji)}</div>
        </span>
      `;
      }
      return `
        <span class="mp-badge mp-badge-${escapeHtml(badge.badgeType)}" title="${escapeHtml(badge.title)}">
          <img
            class="badge-icon"
            src="/static/icons/badges/${encodeURIComponent(badge.code)}.svg"
            alt="${escapeHtml(badge.title)}"
            loading="lazy"
            onerror="this.style.display='none';this.parentElement.classList.add('is-fallback');"
          >
        </span>
      `;
    })
    .join("");
}

function renderMemberCard(member, index = 0) {
  const card = document.createElement("article");
  const fullName = member.full_name || "Участник";
  const company = stripTrailingIndex(member.company || member.company_name || "—");
  const industry = stripTrailingIndex(member.industry || "—");
  const subtitle = [company, industry].filter((value) => value && value !== "—").join(" · ") || "—";
  const annualRevenue = formatRevenue(member.annual_revenue || "—");
  const employeeCount = member.employee_count ?? "—";
  const clubRequest = stripTrailingIndex(member.club_request || "—");
  const pointsBalance = member.points_balance ?? null;
  const badgesHtml = renderBadges(member, index);

  const isInviteSent = sentInviteMemberIds.has(Number(member.id));
  card.className = "member-preview-card";
  card.dataset.id = String(member.id || "");
  card.setAttribute("tabindex", "0");
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", fullName);

  const avatarHtml = member.photo_url
    ? `<img class="mp-photo" src="${escapeHtml(member.photo_url)}" alt="${escapeHtml(fullName)}" loading="lazy">`
    : `<div class="mp-avatar-fallback">${escapeHtml(initials(fullName) || "?")}</div>`;

  card.innerHTML = `
    <div class="mp-left">
      <div class="mp-name">${escapeHtml(fullName)}</div>
      <div class="mp-sub">${escapeHtml(subtitle)}</div>
      <div class="mp-metrics">
        <span class="metric-chip">Оборот: ${escapeHtml(String(annualRevenue))}</span>
        <span class="metric-chip">Сотрудники: ${escapeHtml(String(employeeCount))}</span>
      </div>
      <div class="mp-req">
        <div class="mp-label">Запрос к клубу</div>
        <div class="mp-text">${escapeHtml(String(clubRequest))}</div>
      </div>
      ${badgesHtml ? `<div class="mp-badges">${badgesHtml}</div>` : ""}
      ${pointsBalance !== null ? `<div class="mp-points">Баланс: ${escapeHtml(String(pointsBalance))}</div>` : ""}
    </div>
    <div class="mp-right">
      ${avatarHtml}
      <button class="mp-invite-btn" type="button" ${isInviteSent ? "disabled" : ""}>
        ${isInviteSent
          ? '<span class="mp-invite-label">Запрос отправлен</span>'
          : '<span class="mp-invite-icon" aria-hidden="true">⚡</span><span class="mp-invite-label">Позвать</span>'}
      </button>
    </div>
  `;

  const inviteBtn = card.querySelector(".mp-invite-btn");
  if (inviteBtn) {
    inviteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openInviteModal(member);
    });
  }

  card.addEventListener("click", () => openMemberProfile(member));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openMemberProfile(member);
    }
  });

  return card;
}

async function loadAndRenderMembers(list) {
  renderLoading(list);

  try {
    const members = await fetchMembers();
    latestMembers = members;
    if (!members.length) {
      renderEmpty(list);
      const count = document.getElementById("communityCountBadge");
      if (count) count.textContent = "0 участников";
      return;
    }

    list.innerHTML = "";
    members.forEach((member, index) => list.appendChild(renderMemberCard(member, index)));

    const count = document.getElementById("communityCountBadge");
    if (count) count.textContent = `${members.length} участников`;
  } catch (error) {
    console.error("Failed to load community members", error);
    renderError(list);
    const retryBtn = document.getElementById("communityRetryBtn");
    if (retryBtn) retryBtn.addEventListener("click", () => loadAndRenderMembers(list), { once: true });
  }
}

export function initCommunityScreen() {
  const list = document.getElementById("communityList");
  if (!list) return;
  window.openInviteModal = (memberId) => {
    const target = latestMembers.find((item) => Number(item.id) === Number(memberId));
    if (target) openInviteModal(target);
  };
  loadAndRenderMembers(list);
}




