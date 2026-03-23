import { buildInitDataObject, escapeHtml, getTgId } from "../utils.js";
import { getDevUserHeader, isDevModeActive } from "./dev-user-switcher.js";

const API_TOKEN_KEY = "meeteat_api_token";

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
  return params.toString() || null;
}

async function ensureApiToken() {
  if (await resolveDevMode()) return null;

  const cached = localStorage.getItem(API_TOKEN_KEY);
  if (cached) return cached;

  const initData = getInitDataString();
  if (!initData) {
    throw new Error("Нет данных Telegram для авторизации");
  }

  const response = await fetch("/api/auth/telegram", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Auth failed: ${response.status}${text ? ` ${text}` : ""}`);
  }

  const data = await response.json().catch(() => null);
  const token = data?.token;
  if (!token) throw new Error("Пустой токен авторизации");
  localStorage.setItem(API_TOKEN_KEY, token);
  return token;
}

async function requestWithOptionalAuth(url, options = {}) {
  const isDevMode = await resolveDevMode();
  const devHeaders = isDevMode ? await getDevUserHeader() : {};
  const baseHeaders = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...devHeaders,
    ...(options.headers || {}),
  };

  if (isDevMode) {
    return fetch(url, {
      ...options,
      headers: baseHeaders,
      cache: "no-store",
    });
  }

  let token = null;
  try {
    token = await ensureApiToken();
  } catch (_) {
    token = null;
  }

  const doFetch = async (headers) =>
    fetch(url, {
      ...options,
      headers,
      cache: "no-store",
    });

  let response;
  if (token) {
    response = await doFetch({ ...baseHeaders, Authorization: `Bearer ${token}` });
    if (response.status === 401) {
      localStorage.removeItem(API_TOKEN_KEY);
      token = null;
    }
  }

  if (!response) {
    response = await doFetch(baseHeaders);
  }

  return response;
}

async function requestJsonWithOptionalAuth(url, options = {}) {
  const response = await requestWithOptionalAuth(url, options);
  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  const data = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);
  return { response, data };
}

function getErrorDetail(response, payload) {
  if (payload && typeof payload === "object" && payload.detail) return String(payload.detail);
  if (typeof payload === "string" && payload.trim()) return payload.trim();
  return `HTTP ${response?.status || "error"}`;
}

function parseTagInput(raw) {
  return String(raw || "")
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseTextList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }

  const raw = String(value || "").trim();
  if (!raw) return [];

  if (raw.startsWith("[") && raw.endsWith("]")) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item || "").trim()).filter(Boolean);
      }
    } catch (_) {
      // fall through to plain split
    }
  }

  return raw
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function uniqueList(items) {
  return Array.from(new Set(items.filter(Boolean)));
}

function getInitials(fullName, username = "") {
  const fromName = String(fullName || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((chunk) => chunk[0]?.toUpperCase() || "")
    .join("");
  if (fromName) return fromName;
  const safeUsername = String(username || "").replace(/^@/, "").trim();
  return safeUsername ? safeUsername.slice(0, 2).toUpperCase() : "U";
}

function safeText(value, fallback = "Не заполнено") {
  const text = String(value || "").trim();
  return text || fallback;
}

function safeMarkup(value, fallback = "Не заполнено") {
  return escapeHtml(safeText(value, fallback));
}

function formatRevenue(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/[₸]|тг/i.test(raw)) return raw;
  if (/млн/i.test(raw)) return `${raw} ₸`;
  return raw;
}

function computeCompletion(profile) {
  const fields = [
    profile.full_name,
    profile.photo_url,
    profile.city,
    profile.company,
    profile.position,
    profile.industry,
    profile.annual_revenue,
    profile.employee_count,
    profile.bio,
    profile.goal_2025,
    profile.club_request,
    profile.help_offer,
    profile.core_competencies,
    profile.hobbies,
  ];
  const filled = fields.filter((value) => {
    if (typeof value === "number") return true;
    return String(value || "").trim().length > 0;
  }).length;
  return Math.max(14, Math.round((filled / fields.length) * 100));
}

function buildSubtitle(profile) {
  return [profile.company, profile.position].filter(Boolean).join(" · ") || "Участник Club 999";
}

function buildHeroChips(profile) {
  const chips = [];
  if (profile.city) chips.push(profile.city);
  if (profile.industry) chips.push(profile.industry);
  if (profile.annual_revenue) chips.push(formatRevenue(profile.annual_revenue));
  if (profile.employee_count) chips.push(`Сотрудники: ${profile.employee_count}`);
  if (profile.visibility) {
    const visibilityMap = {
      members_only: "Только для клуба",
      public: "Публичный",
      hidden: "Скрытый",
    };
    chips.push(visibilityMap[profile.visibility] || profile.visibility);
  }
  return chips;
}

function renderAvatar(profile, className, fallbackClass) {
  const initials = getInitials(profile.full_name, profile.tg_username);
  if (profile.photo_url) {
    return `<img class="${className}" src="${escapeHtml(profile.photo_url)}" alt="${escapeHtml(profile.full_name || "Профиль")}" loading="lazy">`;
  }
  return `<div class="${fallbackClass}">${escapeHtml(initials)}</div>`;
}

function renderChipCloud(items, emptyText) {
  if (!items.length) {
    return `<div class="profile-empty-copy">${escapeHtml(emptyText)}</div>`;
  }
  return `
    <div class="profile-chip-cloud">
      ${items.map((item) => `<span class="profile-chip">${escapeHtml(item)}</span>`).join("")}
    </div>
  `;
}

function renderContactRows(contacts) {
  const entries = [
    ["Telegram", contacts.telegram],
    ["Instagram", contacts.instagram],
    ["Website", contacts.website],
    ["Телефон", contacts.phone],
    ["Email", contacts.email],
  ].filter(([, value]) => String(value || "").trim());

  if (!entries.length) {
    return `<div class="profile-empty-copy">Контакты пока не добавлены.</div>`;
  }

  return `
    <div class="profile-contact-list">
      ${entries.map(([label, value]) => `
        <div class="profile-contact-row">
          <span class="profile-contact-label">${escapeHtml(label)}</span>
          <span class="profile-contact-value">${escapeHtml(String(value || "").trim())}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderActivityIcon(kind) {
  const common = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';

  if (kind === "one_on_one") {
    return `<svg ${common} aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/><circle cx="9.5" cy="7" r="3"/><path d="M20 8v6"/><path d="M17 11h6"/></svg>`;
  }

  if (kind === "group_events") {
    return `<svg ${common} aria-hidden="true"><path d="M16 3v4"/><path d="M8 3v4"/><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18"/><path d="M8 14h3"/><path d="M13 14h3"/></svg>`;
  }

  if (kind === "badges") {
    return `<svg ${common} aria-hidden="true"><circle cx="12" cy="8" r="5"/><path d="m8.5 13.5-1 7 4.5-2.5 4.5 2.5-1-7"/></svg>`;
  }

  return `<svg ${common} aria-hidden="true"><path d="M12 3 9.5 9H14l-2 12 6-10h-4.5L16 3z"/></svg>`;
}

function normalizeMetric(value) {
  if (value === undefined || value === null || value === "") return "—";
  return escapeHtml(String(value));
}

function renderActivitySection(activity) {
  const items = [
    { icon: "one_on_one", value: activity.oneOnOne, label: "1-на-1 встречи" },
    { icon: "group_events", value: activity.groupEvents, label: "Групповые события" },
    { icon: "badges", value: activity.badges, label: "Бейджи" },
    { icon: "points", value: activity.points, label: "Баллы" },
  ];

  return `
    <section class="profile-section-card">
      <h3 class="profile-section-title">Активность в клубе</h3>
      <div class="profile-activity-grid">
        ${items.map((item) => `
          <article class="profile-activity-card">
            <div class="profile-activity-icon">${renderActivityIcon(item.icon)}</div>
            <div class="profile-activity-value">${normalizeMetric(item.value)}</div>
            <div class="profile-activity-label">${escapeHtml(item.label)}</div>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function normalizeLegacyProfile(payload) {
  const user = payload?.user || {};
  return {
    full_name: user.name || user.username || "Пользователь",
    tg_username: user.username || "",
    photo_url: user.avatar || "",
    city: "",
    company: "",
    position: "",
    industry: "",
    annual_revenue: "",
    employee_count: null,
    core_competencies: "",
    goal_2025: "",
    club_request: "",
    hobbies: Array.isArray(payload?.tags) ? payload.tags.join(", ") : "",
    help_offer: "",
    bio: "",
    help_tags: [],
    need_tags: Array.isArray(payload?.tags) ? payload.tags : [],
    contacts: {},
    visibility: "members_only",
    status: "active",
  };
}

async function fetchLegacyProfile() {
  const tgId = getTgId();
  if (!tgId) return null;
  const response = await fetch(`/api/profile?tg_id=${encodeURIComponent(tgId)}`, { cache: "no-store" });
  if (!response.ok) return null;
  const payload = await response.json().catch(() => null);
  if (!payload?.ok) return null;
  return normalizeLegacyProfile(payload);
}

async function fetchMyProfile() {
  const { response, data } = await requestJsonWithOptionalAuth("/api/users/me");
  if (response.ok && data && typeof data === "object") {
    const fullName = String(data.full_name || "").trim();
    const username = String(data.tg_username || "").trim();
    return {
      ...data,
      full_name: fullName || username || "Пользователь",
      company: data.company || data.company_name || "",
      position: data.position || "",
      industry: data.industry || "",
      annual_revenue: data.annual_revenue || "",
      core_competencies: data.core_competencies || "",
      goal_2025: data.goal_2025 || "",
      club_request: data.club_request || "",
      hobbies: data.hobbies || "",
      help_offer: data.help_offer || "",
      bio: data.bio || "",
      help_tags: Array.isArray(data.help_tags) ? data.help_tags : [],
      need_tags: Array.isArray(data.need_tags) ? data.need_tags : [],
      contacts: data.contacts && typeof data.contacts === "object" ? data.contacts : {},
      visibility: data.visibility || "members_only",
    };
  }

  const fallback = await fetchLegacyProfile();
  if (fallback) return fallback;

  throw new Error(getErrorDetail(response, data));
}

async function fetchProfileActivity() {
  const [dashboardResult, badgesResult, storeResult] = await Promise.allSettled([
    requestJsonWithOptionalAuth("/api/lightning/dashboard"),
    requestJsonWithOptionalAuth("/api/badges/me"),
    requestJsonWithOptionalAuth("/api/store/summary"),
  ]);

  const dashboardData = dashboardResult.status === "fulfilled" && dashboardResult.value.response.ok
    ? dashboardResult.value.data
    : null;
  const badgesData = badgesResult.status === "fulfilled" && badgesResult.value.response.ok
    ? badgesResult.value.data
    : null;
  const storeData = storeResult.status === "fulfilled" && storeResult.value.response.ok
    ? storeResult.value.data
    : null;
  const hasDashboard = Boolean(dashboardData && typeof dashboardData === "object");

  return {
    oneOnOne: hasDashboard
      ? (Array.isArray(dashboardData?.outgoing_requests) ? dashboardData.outgoing_requests.length : 0) +
        (Array.isArray(dashboardData?.incoming_requests) ? dashboardData.incoming_requests.length : 0)
      : "—",
    groupEvents: hasDashboard
      ? (Array.isArray(dashboardData?.group_meetings) ? dashboardData.group_meetings.length : 0) +
        (Array.isArray(dashboardData?.club_events) ? dashboardData.club_events.length : 0)
      : "—",
    badges: Array.isArray(badgesData) ? badgesData.length : "—",
    points: typeof storeData?.points === "number" ? storeData.points : "—",
  };
}

function renderProfileView(profile, activity) {
  const completion = computeCompletion(profile);
  const competencies = uniqueList([
    ...parseTextList(profile.core_competencies),
    ...parseTextList(profile.help_tags),
  ]);
  const hobbies = uniqueList([
    ...parseTextList(profile.hobbies),
    ...parseTextList(profile.need_tags),
  ]);
  const chips = buildHeroChips(profile);
  const subtitle = buildSubtitle(profile);

  return `
    <div class="profile-page-header">
      <h2 class="profile-page-title">Профиль</h2>
      <p class="profile-page-subtitle">Ваш профиль в Club 999 и LunchFlowKZ</p>
    </div>

    <section class="profile-hero-card">
      <div class="profile-hero-top">
        ${renderAvatar(profile, "profile-hero-avatar", "profile-hero-avatar-fallback")}
        <div class="profile-hero-copy">
          <div class="profile-hero-name">${escapeHtml(profile.full_name || "Пользователь")}</div>
          <div class="profile-hero-subtitle">${escapeHtml(subtitle)}</div>
          <div class="profile-hero-meta">Профиль заполнен на ${escapeHtml(String(completion))}%</div>
        </div>
        <button type="button" id="profileEditAction" class="profile-hero-edit-btn">Редактировать</button>
      </div>
      ${chips.length ? `<div class="profile-hero-chip-row">${chips.map((chip) => `<span class="profile-hero-chip">${escapeHtml(chip)}</span>`).join("")}</div>` : ""}
    </section>

    ${renderActivitySection(activity)}

    <section class="profile-section-card">
      <h3 class="profile-section-title">О себе</h3>
      <div class="profile-section-eyebrow">${escapeHtml(profile.company ? `Компания: ${profile.company}` : "Профиль участника")}</div>
      <p class="profile-section-copy">${safeMarkup(profile.bio, "Добавьте короткое описание, чтобы другим участникам было проще понять, чем вы занимаетесь.")}</p>
    </section>

    <section class="profile-section-card">
      <div class="profile-copy-block">
        <h4 class="profile-copy-title">Цель на год</h4>
        <p class="profile-section-copy">${safeMarkup(profile.goal_2025, "Цель на год пока не добавлена.")}</p>
      </div>
      <div class="profile-copy-block">
        <h4 class="profile-copy-title">Запрос к клубу</h4>
        <p class="profile-section-copy">${safeMarkup(profile.club_request, "Запрос к клубу пока не заполнен.")}</p>
      </div>
      <div class="profile-copy-block">
        <h4 class="profile-copy-title">Чем могу помочь</h4>
        <p class="profile-section-copy">${safeMarkup(profile.help_offer, "Расскажите, чем можете быть полезны другим участникам.")}</p>
      </div>
    </section>

    <section class="profile-section-card">
      <h3 class="profile-section-title">Компетенции</h3>
      ${renderChipCloud(competencies, "Компетенции пока не добавлены.")}
    </section>

    <section class="profile-section-card">
      <h3 class="profile-section-title">Интересы и хобби</h3>
      ${renderChipCloud(hobbies, "Интересы пока не добавлены.")}
    </section>

    <section class="profile-section-card">
      <h3 class="profile-section-title">Контакты</h3>
      ${renderContactRows(profile.contacts || {})}
    </section>
  `;
}

function renderProfileEdit(profile) {
  const helpTags = parseTextList(profile.help_tags).join(", ");
  const needTags = parseTextList(profile.need_tags).join(", ");
  const contacts = profile.contacts || {};

  return `
    <div class="profile-page-header">
      <h2 class="profile-page-title">Редактировать профиль</h2>
      <p class="profile-page-subtitle">Обновите поля профиля, которые уже поддерживаются в приложении</p>
    </div>

    <form id="profileEditFormModern" class="profile-edit-form" novalidate>
      <section class="profile-section-card">
        <div class="profile-edit-photo-row">
          ${renderAvatar(profile, "profile-edit-avatar", "profile-edit-avatar-fallback")}
          <div class="profile-edit-photo-copy">
            <h3 class="profile-section-title">Основная информация</h3>
            <p class="profile-edit-hint">Фото и имя участвуют в карточках участника, встречах и навигации по клубу.</p>
          </div>
        </div>
        <div class="profile-form-grid profile-form-grid-two">
          <label class="profile-field">
            <span>Полное имя</span>
            <input id="editFullName" type="text" value="${escapeHtml(profile.full_name || "")}" placeholder="Например, Maydan Serikov">
          </label>
          <label class="profile-field">
            <span>Фото профиля URL</span>
            <input id="editPhotoUrl" type="url" value="${escapeHtml(profile.photo_url || "")}" placeholder="https://...">
          </label>
        </div>
      </section>

      <section class="profile-section-card">
        <h3 class="profile-section-title">Публичная карточка</h3>
        <div class="profile-form-grid profile-form-grid-two">
          <label class="profile-field">
            <span>Город</span>
            <input id="editCity" type="text" value="${escapeHtml(profile.city || "")}" placeholder="Алматы">
          </label>
          <label class="profile-field">
            <span>Компания</span>
            <input id="editCompany" type="text" value="${escapeHtml(profile.company || "")}" placeholder="LunchFlowKZ">
          </label>
          <label class="profile-field">
            <span>Роль / позиция</span>
            <input id="editPosition" type="text" value="${escapeHtml(profile.position || "")}" placeholder="Founder">
          </label>
          <label class="profile-field">
            <span>Индустрия</span>
            <input id="editIndustry" type="text" value="${escapeHtml(profile.industry || "")}" placeholder="Community Tech">
          </label>
          <label class="profile-field">
            <span>Годовой оборот</span>
            <input id="editAnnualRevenue" type="text" value="${escapeHtml(profile.annual_revenue || "")}" placeholder="120-200 млн ₸">
          </label>
          <label class="profile-field">
            <span>Сотрудники</span>
            <input id="editEmployeeCount" type="number" min="0" value="${String(profile.employee_count ?? "")}" placeholder="8">
          </label>
        </div>
        <label class="profile-field">
          <span>О себе</span>
          <textarea id="editBio" rows="4" placeholder="Коротко опишите бизнес и роль в клубе">${escapeHtml(profile.bio || "")}</textarea>
        </label>
      </section>

      <section class="profile-section-card">
        <h3 class="profile-section-title">Контекст клуба</h3>
        <label class="profile-field">
          <span>Цель на год</span>
          <textarea id="editGoal" rows="3" placeholder="Главный фокус на ближайший год">${escapeHtml(profile.goal_2025 || "")}</textarea>
        </label>
        <label class="profile-field">
          <span>Запрос к клубу</span>
          <textarea id="editClubRequest" rows="3" placeholder="Какие знакомства, ресурсы или форматы вам нужны">${escapeHtml(profile.club_request || "")}</textarea>
        </label>
        <label class="profile-field">
          <span>Чем могу помочь</span>
          <textarea id="editHelpOffer" rows="3" placeholder="Чем вы можете быть полезны другим участникам">${escapeHtml(profile.help_offer || "")}</textarea>
        </label>
      </section>

      <section class="profile-section-card">
        <h3 class="profile-section-title">Теги и подборки</h3>
        <label class="profile-field">
          <span>Компетенции</span>
          <textarea id="editCompetencies" rows="3" placeholder="Через запятую">${escapeHtml(profile.core_competencies || "")}</textarea>
        </label>
        <label class="profile-field">
          <span>Интересы и хобби</span>
          <textarea id="editHobbies" rows="3" placeholder="Через запятую">${escapeHtml(profile.hobbies || "")}</textarea>
        </label>
        <label class="profile-field">
          <span>Чем полезен клубу</span>
          <input id="editHelpTags" type="text" value="${escapeHtml(helpTags)}" placeholder="product, growth, strategy">
        </label>
        <label class="profile-field">
          <span>Что ищу в клубе</span>
          <input id="editNeedTags" type="text" value="${escapeHtml(needTags)}" placeholder="networking, investors, partners">
        </label>
      </section>

      <section class="profile-section-card">
        <h3 class="profile-section-title">Контакты и приватность</h3>
        <div class="profile-form-grid profile-form-grid-two">
          <label class="profile-field">
            <span>Telegram</span>
            <input id="editContactTelegram" type="text" value="${escapeHtml(contacts.telegram || "")}" placeholder="@username">
          </label>
          <label class="profile-field">
            <span>Instagram</span>
            <input id="editContactInstagram" type="text" value="${escapeHtml(contacts.instagram || "")}" placeholder="@handle">
          </label>
          <label class="profile-field">
            <span>Website</span>
            <input id="editContactWebsite" type="url" value="${escapeHtml(contacts.website || "")}" placeholder="https://">
          </label>
          <label class="profile-field">
            <span>Email</span>
            <input id="editContactEmail" type="email" value="${escapeHtml(contacts.email || "")}" placeholder="hello@company.kz">
          </label>
        </div>
        <label class="profile-field">
          <span>Видимость профиля</span>
          <select id="editVisibility">
            <option value="members_only" ${profile.visibility === "members_only" ? "selected" : ""}>Только для клуба</option>
            <option value="public" ${profile.visibility === "public" ? "selected" : ""}>Публичный</option>
            <option value="hidden" ${profile.visibility === "hidden" ? "selected" : ""}>Скрытый</option>
          </select>
        </label>
      </section>

      <div class="profile-edit-actions">
        <div id="profileEditStatus" class="profile-edit-status" aria-live="polite"></div>
        <div class="profile-edit-actions-row">
          <button type="button" id="profileEditCancel" class="profile-secondary-btn">Отмена</button>
          <button type="submit" id="profileEditSave" class="profile-primary-btn">Сохранить профиль</button>
        </div>
      </div>
    </form>
  `;
}

function bindAvatarFallbacks(root) {
  root.querySelectorAll("img[data-avatar-fallback]").forEach((img) => {
    img.addEventListener(
      "error",
      () => {
        const fallback = img.getAttribute("data-avatar-fallback");
        if (!fallback) return;
        img.outerHTML = fallback;
      },
      { once: true }
    );
  });
}

function buildAvatarFallbackString(profile, className) {
  return `<div class="${className}">${escapeHtml(getInitials(profile.full_name, profile.tg_username))}</div>`;
}

function attachAvatarFallbackMarkup(root, profile) {
  root.querySelectorAll(".profile-hero-avatar, .profile-edit-avatar").forEach((img) => {
    if (!(img instanceof HTMLImageElement)) return;
    const className = img.classList.contains("profile-edit-avatar")
      ? "profile-edit-avatar-fallback"
      : "profile-hero-avatar-fallback";
    img.dataset.avatarFallback = buildAvatarFallbackString(profile, className);
  });
  bindAvatarFallbacks(root);
}

export async function initProfileScreen({ navigate }) {
  const root = document.getElementById("profileScreenRoot");
  if (!root) return;

  root.innerHTML = '<div class="profile-loading-card">Загрузка профиля...</div>';

  try {
    const [profile, activity] = await Promise.all([
      fetchMyProfile(),
      fetchProfileActivity(),
    ]);
    root.innerHTML = renderProfileView(profile, activity);
    attachAvatarFallbackMarkup(root, profile);

    const editBtn = root.querySelector("#profileEditAction");
    if (editBtn) {
      editBtn.addEventListener("click", () => navigate("profile_edit"));
    }
  } catch (error) {
    console.error("profile screen load failed", error);
    root.innerHTML = `
      <div class="profile-error-card">
        <div class="profile-error-title">Не удалось загрузить профиль</div>
        <div class="profile-error-text">${escapeHtml(error instanceof Error ? error.message : "Попробуйте ещё раз")}</div>
        <button type="button" id="profileRetryBtn" class="profile-primary-btn">Повторить</button>
      </div>
    `;
    const retryBtn = root.querySelector("#profileRetryBtn");
    if (retryBtn) {
      retryBtn.addEventListener("click", () => initProfileScreen({ navigate }));
    }
  }
}

export async function initProfileEditScreen({ navigate }) {
  const root = document.getElementById("profileEditRoot");
  if (!root) return;

  root.innerHTML = '<div class="profile-loading-card">Загрузка формы...</div>';

  try {
    const profile = await fetchMyProfile();
    root.innerHTML = renderProfileEdit(profile);
    attachAvatarFallbackMarkup(root, profile);

    const form = root.querySelector("#profileEditFormModern");
    const cancelBtn = root.querySelector("#profileEditCancel");
    const saveBtn = root.querySelector("#profileEditSave");
    const statusEl = root.querySelector("#profileEditStatus");

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => navigate("profile"));
    }

    if (!(form instanceof HTMLFormElement) || !(saveBtn instanceof HTMLButtonElement)) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      saveBtn.disabled = true;
      if (statusEl) statusEl.textContent = "Сохраняем...";

      const employeeRaw = String(root.querySelector("#editEmployeeCount")?.value || "").trim();
      const employeeCount = employeeRaw === "" ? null : Number(employeeRaw);
      const contacts = {
        telegram: String(root.querySelector("#editContactTelegram")?.value || "").trim(),
        instagram: String(root.querySelector("#editContactInstagram")?.value || "").trim(),
        website: String(root.querySelector("#editContactWebsite")?.value || "").trim(),
        email: String(root.querySelector("#editContactEmail")?.value || "").trim(),
      };

      Object.keys(contacts).forEach((key) => {
        if (!contacts[key]) delete contacts[key];
      });

      const payload = {
        full_name: String(root.querySelector("#editFullName")?.value || "").trim(),
        photo_url: String(root.querySelector("#editPhotoUrl")?.value || "").trim(),
        city: String(root.querySelector("#editCity")?.value || "").trim(),
        company: String(root.querySelector("#editCompany")?.value || "").trim(),
        position: String(root.querySelector("#editPosition")?.value || "").trim(),
        industry: String(root.querySelector("#editIndustry")?.value || "").trim(),
        annual_revenue: String(root.querySelector("#editAnnualRevenue")?.value || "").trim(),
        employee_count: Number.isFinite(employeeCount) ? employeeCount : null,
        bio: String(root.querySelector("#editBio")?.value || "").trim(),
        goal_2025: String(root.querySelector("#editGoal")?.value || "").trim(),
        club_request: String(root.querySelector("#editClubRequest")?.value || "").trim(),
        help_offer: String(root.querySelector("#editHelpOffer")?.value || "").trim(),
        core_competencies: String(root.querySelector("#editCompetencies")?.value || "").trim(),
        hobbies: String(root.querySelector("#editHobbies")?.value || "").trim(),
        help_tags: parseTagInput(root.querySelector("#editHelpTags")?.value || ""),
        need_tags: parseTagInput(root.querySelector("#editNeedTags")?.value || ""),
        contacts,
        visibility: String(root.querySelector("#editVisibility")?.value || "members_only"),
      };

      try {
        const { response, data } = await requestJsonWithOptionalAuth("/api/users/me", {
          method: "PATCH",
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(getErrorDetail(response, data));
        }

        if (payload.full_name) {
          localStorage.setItem("meeteat_name", payload.full_name);
        } else {
          localStorage.removeItem("meeteat_name");
        }

        if (payload.photo_url) {
          localStorage.setItem("meeteat_avatar", payload.photo_url);
        } else {
          localStorage.removeItem("meeteat_avatar");
        }

        if (statusEl) statusEl.textContent = "Профиль сохранён";
        navigate("profile");
      } catch (error) {
        console.error("profile save failed", error);
        if (statusEl) {
          statusEl.textContent = error instanceof Error ? error.message : "Не удалось сохранить профиль";
        }
      } finally {
        saveBtn.disabled = false;
      }
    });
  } catch (error) {
    console.error("profile edit load failed", error);
    root.innerHTML = `
      <div class="profile-error-card">
        <div class="profile-error-title">Не удалось открыть редактирование</div>
        <div class="profile-error-text">${escapeHtml(error instanceof Error ? error.message : "Попробуйте ещё раз")}</div>
        <button type="button" id="profileEditRetryBtn" class="profile-primary-btn">Повторить</button>
      </div>
    `;
    const retryBtn = root.querySelector("#profileEditRetryBtn");
    if (retryBtn) {
      retryBtn.addEventListener("click", () => initProfileEditScreen({ navigate }));
    }
  }
}
