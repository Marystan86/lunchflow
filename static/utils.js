// static/utils.js

// Константы
const API_ROOT = "";
const DEFAULT_TAGS = [
    "бизнес", "IT", "стартапы", "AI", "программирование","веб","frontend",
    "backend","data-science","машинное обучение","дизайн","фотография",
    "спорт","фитнес","йога","путешествия","еда","кофе","кино",
    "музыка","книги","игры","технологии","стартап-менеджмент","маркетинг"
];

const reactions = [
    { emoji: "🙂", label: "Приятный собеседник" },
    { emoji: "🧠", label: "Мыслит нестандартно" },
    { emoji: "🤝", label: "Крутой нетворкер" },
    { emoji: "🔥", label: "Любит свое дело" },
    { emoji: "⚡", label: "Позитивный и энергичный" },
];


// UI helpers
function hideShareButton() {
    const b = $qs("#shareGeoBtn");
    if (b) b.classList.remove("visible"), b.classList.add("hidden");
}

function showShareButton() {
    const b = $qs("#shareGeoBtn");
    if (b) b.classList.remove("hidden");
}

// API и запросы
async function postJson(path, body) {
    const res = await fetch(API_ROOT + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const text = await res.text().catch(()=>null);
        throw new Error("HTTP " + res.status + (text ? " - " + text : ""));
    }
    return res.json();
}

// Парсинг и Telegram init
function parseInnerQuery(str) {
    if (!str) return {};
    if (str.startsWith("?") || str.startsWith("#")) str = str.slice(1);
    const params = new URLSearchParams(str);
    const obj = {};
    for (const [k,v] of params.entries()) obj[k] = v;
    // keep "user" as decoded JSON string (do not parse to object)
    if (obj.user) {
        try {
            obj.user = decodeURIComponent(obj.user);
        } catch (e) {}
    }
    return obj;
}

function extractTgWebAppDataFromUrl() {
    const tryParams = (s) => {
        if (!s) return null;
        const idx = s.indexOf("tgWebAppData=");
        if (idx === -1) return null;
        let tail = s.slice(idx + "tgWebAppData=".length);
        const htmlPos = tail.indexOf(".html");
        if (htmlPos !== -1) tail = tail.slice(0, htmlPos);
        try { return decodeURIComponent(tail); } catch(e) { return tail; }
    };
    let raw = tryParams(location.search);
    if (raw) return parseInnerQuery(raw);
    raw = tryParams(location.hash);
    if (raw) return parseInnerQuery(raw);
    raw = tryParams(location.pathname);
    if (raw) return parseInnerQuery(raw);
    return null;
}

function buildInitDataObject() {
    // prefer initData string if present
    const initStr = window.Telegram?.WebApp?.initData ?? null;
    if (initStr && typeof initStr === "string" && initStr.includes("=")) {
        return parseInnerQuery(initStr);
    }
    // if we only have tgWebAppData in URL
    const parsedFromUrl = extractTgWebAppDataFromUrl();
    if (parsedFromUrl) return parsedFromUrl;
    // if we only have unsafe object (last resort)
    const initUnsafe = window.Telegram?.WebApp?.initDataUnsafe ?? null;
    if (initUnsafe && typeof initUnsafe === "object") {
        // best-effort: convert fields to strings; keep user as JSON string
        const out = {};
        for (const k of Object.keys(initUnsafe)) {
            if (k === "user" && initUnsafe.user) {
                try { out.user = JSON.stringify(initUnsafe.user); }
                catch(e) { out.user = String(initUnsafe.user); }
            } else {
                out[k] = String(initUnsafe[k]);
            }
        }
        return out;
    }
    return null;
}

async function verifyInitData(initData) {
    return postJson("/verify_init", { initData })
        .catch(err => ({ ok: false, error: err.message }));
}

// Хранение
function saveTgId(tg_id) {
    localStorage.setItem("meeteat_tg_id", String(tg_id));
}

function getTgId() {
    return localStorage.getItem("meeteat_tg_id") ? Number(localStorage.getItem("meeteat_tg_id")) : null;
}

async function ensureTgId() {
    const saved = getTgId();
    if (saved) return saved;
    // prefer raw initData string if available
    const rawInit = window.Telegram?.WebApp?.initData ?? null;
    let initData = rawInit ? rawInit : buildInitDataObject();
    if (initData) {
        const resp = await verifyInitData(initData).catch(() => ({ ok:false }));
        if (resp && resp.ok && resp.tg_id) {
            saveTgId(resp.tg_id);
            if (resp.name) localStorage.setItem("meeteat_name", resp.name);
            if (resp.username) localStorage.setItem("meeteat_username", resp.username);
            if (resp.avatar) localStorage.setItem("meeteat_avatar", resp.avatar);
            // Синхронизируем профиль (await чтобы гарантировать запись до дальнейших действий, можно убрать await если не надо блокировать)
            (async () => {
                try {
                    // отправляем только существующие поля
                    const payload = { tg_id: resp.tg_id };
                    if (resp.name) payload.name = resp.name;
                    if (resp.username) payload.username = resp.username;
                    if (resp.avatar) payload.avatar = resp.avatar;
                    await postJson("/api/profile/update", payload);
                } catch (err) {
                    console.warn("profile sync failed", err);
                }
            })();
            showShareButton(); // Это UI, но оставил, так как связано с auth
        } else {
            console.warn("verifyInitData failed", resp);
        }
    }
    alert("tg_id не найден. Откройте в Telegram или сохраните tg_id для теста.");
    return null;
}

// DOM и escape
function $qs(sel) {
    return document.querySelector(sel);
}

function escapeHtml(s) {
    if (!s) return "";
    return String(s).replace(/[&<>"']/g, function(m) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m];
    });
}

// Экспорты
export {
    API_ROOT, DEFAULT_TAGS, reactions,
    hideShareButton, showShareButton,
    postJson, parseInnerQuery, extractTgWebAppDataFromUrl, buildInitDataObject,
    verifyInitData, saveTgId, getTgId, ensureTgId,
    $qs, escapeHtml
};