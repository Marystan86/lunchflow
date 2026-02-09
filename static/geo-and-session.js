// static/geo-and-session.js

import {
    API_ROOT, DEFAULT_TAGS, reactions,
    hideShareButton, showShareButton,
    postJson, parseInnerQuery, extractTgWebAppDataFromUrl, buildInitDataObject,
    verifyInitData, saveTgId, getTgId, ensureTgId,
    $qs, escapeHtml
} from './utils.js';

import {
    renderPersonCard, renderInterestCard, fetchSimilarAndRender,
    fetchReviewsFor, renderRecentReviews,
    fetchAvailableTags, openTagModal, closeTagModal,
    formatDatetimeLocal, getTomorrowAt, openInviteModal, insertAfter,
    openUserProfilePage, loadScreen, runScreenInit,
    tryAutoStart
} from "./ui-and-screens.js";

function parseServerDatetime(s) {
    if (!s) return null;

    // если уже ISO
    if (s.includes("T") || s.endsWith("Z")) {
        const d = new Date(s);
        return isNaN(d) ? null : d;
    }
    
    // формат "YYYY-MM-DD HH:MM:SS" -> сделать ISO UTC
    const iso = s.replace(" ", "T") + "Z";
    const d = new Date(iso);
    return isNaN(d) ? null : d;
}


// Геолокация helpers
function getCurrentPositionPromise(options = { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }) {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error("Geolocation not supported"));
        navigator.geolocation.getCurrentPosition(pos => resolve(pos), err => reject(err), options);
    });
}

function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

function randomDelayMs(min = 3000, max = 5000) {
    return Math.floor(min + Math.random() * (max - min + 1));
}

// Радар
function startRadarRings(count = 3) {
    const el = getEatCircle();
    if (!el) return;

    // убираем старые кольца (с запасом)
    if (el._radarRings && el._radarRings.length) {
        for (const rr of el._radarRings) try{ rr.remove(); }catch(e){}
    }

    el._radarActive = true;
    el._radarRings = [];
    const duration = 2000;
    const gap = duration / count;
    for (let i = 0; i < count; i++) {
        const r = document.createElement("div");
        r.className = "radar-ring ring-" + i;
        r.style.setProperty("--radar-delay", (i * (gap / 1000)).toFixed(3) + "s");
        r.style.animationDuration = duration + "ms";
        el.appendChild(r);
        el._radarRings.push(r);
    }
}

function stopRadarRings() {
    const el = getEatCircle();
    if (!el || !el._radarActive) return;
    const rings = el._radarRings || [];
    for (const r of rings) {
        try { r.style.transition = "opacity 250ms linear"; r.style.opacity = "0"; } catch(e){}
        setTimeout(() => { try { r.remove(); } catch(e){} }, 300);
    }
    el._radarRings = [];
    el._radarActive = false;
}


// Eat circle и hints
function showEatHint(text) {
    const el = $qs("#eatHint");
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("hidden");
}

function hideEatHint() {
    const el = $qs("#eatHint");
    if (!el) return;
    el.classList.add("hidden");
}

function getEatCircle() {
    return $qs("#eatCircle");
}

function setEatCircleSearching(on) {
    const el = getEatCircle();
    if (!el) return;
    if (on) {
        el.classList.add("searching");
        startRadarRings(3);
    } else {
        el.classList.remove("searching");
        stopRadarRings();
    }
}

function setEatCircleActive(on) {
    const el = getEatCircle();
    if (!el) return;
    if (on) {
        el.classList.add("active");
        el.setAttribute("aria-pressed", "true");
    } else {
        el.classList.remove("active");
        el.classList.remove("searching");
        el.setAttribute("aria-pressed", "false");
    }
}

// Сессии
async function startEatingWithDelay() {
    // проверяем tg_id / авторизацию как в startEating
    const rawInit = window.Telegram?.WebApp?.initData ?? null;
    const initData = rawInit ? rawInit : buildInitDataObject();
    let verified;
    if (initData) {
        verified = await verifyInitData(initData);
    } else {
        const saved = localStorage.getItem("meeteat_tg_id");
        if (saved) verified = { ok: true, tg_id: Number(saved) };
        else {
            alert("Откройте приложение через Telegram, либо сохраните tg_id для теста.");
            return;
        }
    }
    if (!verified.ok) { alert("Auth failed"); return; }
    const tg_id = verified.tg_id;
    saveTgId(tg_id);
    
    // UI: показываем что ищем
    setEatCircleSearching(true);
    showEatHint("Ищем людей поблизости…");

    // параллельно: геопозиция и искусственная задержка
    const delayMs = randomDelayMs(3000, 5000);
    const delayP = sleep(delayMs);
    const posP = getCurrentPositionPromise({ enableHighAccuracy: true, maximumAge: 0, timeout: 10000 });
    let pos;
    try {
        // ждём обе операции: геопозиция и задержку
        const [position] = await Promise.all([ posP.catch(e => { throw e; }), delayP ]);
        pos = position;
    } catch (geoErr) {
        console.warn("geo error during delayed start", geoErr);
        setEatCircleSearching(false);
        showEatHint("Нажми на кнопку, чтобы найти людей рядом");
        if (geoErr && geoErr.code === 1) alert("Доступ к геопозиции запрещён пользователем.");
        else if (geoErr && geoErr.code === 3) alert("Таймаут получения геопозиции. Попробуйте снова.");
        else alert("Не удалось получить геопозицию: " + (geoErr.message || geoErr));
        return;
    }

    // если получили позицию - отправляем /start и запускаем nearby
    try {
        const body = { tg_id, lat: pos.coords.latitude, lon: pos.coords.longitude };
        const data = await postJson("/start", body);
        
        // render nearby
        await fetchNearbyAndRender(tg_id, body.lat, body.lon);
        
        // запустить таймер и UI
        showEatStatus(data.expires_at);
        showTimerAndUi(data.expires_at);
        startUpdateLoop(tg_id);
        setEatCircleActive(true);
        hideEatHint();
    } catch (e) {
        console.error("startWithDelay failed", e);
        alert("Ошибка при запуске: " + (e.message || e));
        setEatCircleSearching(false);
        showEatHint("Нажми на кнопку, чтобы найти людей рядом");
    } finally {
        setEatCircleSearching(false);
    }
}

let eatStatusIntervalId = null;
// function showEatStatus(expires_iso) {
//     const el = $qs("#eatStatus");
//     const timerEl = $qs("#eatStatusTimer");
//     if (!el || !timerEl) return;

//     // прячем кнопку
//     hideShareButton();
//     el.classList.remove("hidden");
    
//     // очищаем старый интервал
//     if (eatStatusIntervalId) {
//         clearInterval(eatStatusIntervalId);
//         eatStatusIntervalId = null;
//     }

//     function tick() {
//         const expires = new Date(expires_iso);
//         const rem = Math.max(0, expires - new Date());
//         const mins = Math.floor(rem / 60000);
//         const secs = Math.floor((rem % 60000) / 1000);
//         const mm = String(mins).padStart(2,"0");
//         const ss = String(secs).padStart(2,"0");
//         timerEl.textContent = `${mm}:${ss}`;
//         if (rem <= 0) {
//             hideEatStatus();
//             showShareButton();
//             stopUpdateLoop();
//             if (eatStatusIntervalId) {
//                 clearInterval(eatStatusIntervalId);
//                 eatStatusIntervalId = null;
//             }
//         }
//     }
//     tick();
//     eatStatusIntervalId = setInterval(tick, 1000);
//     setEatCircleActive(true);
// }

function showEatStatus(expires_iso) {
    const el = $qs("#eatStatus");
    const timerEl = $qs("#eatStatusTimer");
    if (!el || !timerEl) return;

    hideShareButton();
    el.classList.remove("hidden");

    if (eatStatusIntervalId) {
        clearInterval(eatStatusIntervalId);
        eatStatusIntervalId = null;
    }

    const expiresDate = parseServerDatetime(expires_iso);
    if (!expiresDate) {
        timerEl.textContent = "";
        return;
    }

    function tick() {
        const rem = Math.max(0, expiresDate - new Date());
        const mins = Math.floor(rem / 60000);
        const secs = Math.floor((rem % 60000) / 1000);
        timerEl.textContent = `${String(mins).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;
        if (rem <= 0) {
            hideEatStatus();
            showShareButton();
            stopUpdateLoop();
            if (eatStatusIntervalId) {
                clearInterval(eatStatusIntervalId);
                eatStatusIntervalId = null;
            }
        }
    }
    tick();
    eatStatusIntervalId = setInterval(tick, 1000);
    setEatCircleActive(true);
}


function hideEatStatus(){
    setEatCircleActive(false);
    const el = $qs("#eatStatus");
    if (!el) return;
   
    el.classList.add("hidden");
    const timerEl = $qs("#eatStatusTimer");
    if (timerEl) timerEl.textContent = "";
    if (eatStatusIntervalId) {
        clearInterval(eatStatusIntervalId);
        eatStatusIntervalId = null;
    }
}

async function startEating() {
    try {
        const rawInit = window.Telegram?.WebApp?.initData ?? null;
        const initData = rawInit ? rawInit : buildInitDataObject();
        let verified;
        if (initData) {
            verified = await verifyInitData(initData);
        } else {
            const saved = localStorage.getItem("meeteat_tg_id");
            if (saved) verified = { ok: true, tg_id: Number(saved) };
            else return alert("Откройте приложение через Telegram, либо сохраните tg_id для теста.");
        }
        if (!verified.ok) {
            console.error("verify failed", verified);
            return alert("Auth failed");
        }
        const tg_id = verified.tg_id;
        saveTgId(tg_id);
        navigator.geolocation.getCurrentPosition(async pos => {
            const body = { tg_id, lat: pos.coords.latitude, lon: pos.coords.longitude };
            const data = await postJson("/start", body);
            console.log("start:", data);
            startUpdateLoop(tg_id);
            showTimerAndUi(data.expires_at);
            showEatStatus(data.expires_at);
            fetchNearbyAndRender(tg_id, body.lat, body.lon);
        }, err => {
            console.error("geo error", err);
            alert("Не удалось получить геопозицию");
        }, { enableHighAccuracy: true, maximumAge: 5000 });
    } catch (e) {
        console.error(e);
        alert("Ошибка старта: " + e.message);
    }
}

async function stopEating() {
    const tg_id = Number(localStorage.getItem("meeteat_tg_id"));
    if (!tg_id) return alert("tg_id not found");
    try {
        await postJson("/stop", { tg_id });
        stopUpdateLoop();
        hideTimerAndUi();
        hideEatStatus();
        showShareButton();
        alert("Сессия остановлена");
    } catch (e) {
        console.error(e);
        alert("Stop failed");
    }
}

let updateIntervalId = null;
function startUpdateLoop(tg_id) {
    stopUpdateLoop();
    updateIntervalId = setInterval(() => {
        navigator.geolocation.getCurrentPosition(async pos => {
        try {
            await postJson("/start", { tg_id, lat: pos.coords.latitude, lon: pos.coords.longitude });
            console.log("pos updated");
            fetchNearbyAndRender(tg_id, pos.coords.latitude, pos.coords.longitude);
        } catch (e) {
            console.error("update error", e);
        }
        }, err => {
            console.warn("geo failed during update", err);
        }, { enableHighAccuracy: true, maximumAge: 15000 });
    }, 30000);
}

function stopUpdateLoop() {
    if (updateIntervalId) {
        clearInterval(updateIntervalId);
        updateIntervalId = null;
    }
}

// Timer UI
function showTimerAndUi(expires_iso) {
    const expires = parseServerDatetime(expires_iso);
    const timerEl = $qs("#timer");
    if (!timerEl || !expires) return;
    timerEl.style.display = "block";
    let tid = null;
    function tick() {
        const rem = Math.max(0, expires - new Date());
        const mins = Math.floor(rem / 60000);
        const secs = Math.floor((rem % 60000) / 1000);
        timerEl.textContent = `Сессия: ${mins}м ${secs}s`;
        if (rem <= 0) {
            timerEl.textContent = "Сессия завершена";
            stopUpdateLoop();
            if (tid) { clearInterval(tid); tid = null; }
        }
    }
    tick();
    tid = setInterval(tick, 1000);
    timerEl.dataset.tid = String(tid);
}


function hideTimerAndUi() {
    const timerEl = $qs("#timer");
    if (!timerEl) return;
    timerEl.style.display = "none";
    const tid = timerEl.dataset.tid;
    if (tid) clearInterval(Number(tid));
    timerEl.textContent = "";
}

// Nearby
function pluralizePeople(n) {
    if (n === 0) return "0 человек";
    if (n === 1) return "1 человек";
    const rem10 = n % 10;
    if (rem10 >= 2 && rem10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return `${n} человека`;
    return `${n} человек`;
}

async function fetchNearbyAndRender(tg_id, lat, lon, radius_km = 3.0) {
    const countEl = $qs("#nearbyCount");
    const cards = $qs("#nearbyCards");
    if (!countEl || !cards) return;
    cards.innerHTML = '<div class="muted">Ищем людей поблизости…</div>';
    try {
        const res = await fetch(`/nearby?tg_id=${encodeURIComponent(tg_id)}&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&radius_km=${encodeURIComponent(radius_km)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("nearby fetch failed " + res.status);
        const data = await res.json();
        const items = data.nearby || [];

        // update title
        const txt = `Рядом - ${pluralizePeople(items.length)} готовы обедать`;
        countEl.textContent = txt;
        countEl.classList.add("nearby-count--spaced");

        // render cards
        cards.innerHTML = "";
        if (items.length === 0) {
            cards.innerHTML = '<div class="muted">Никого рядом не найдено</div>';
            return;
        }
        for (const p of items) {
            const node = renderPersonCard(p);
            cards.appendChild(node);
        }
    } catch (e) {
        console.error("fetchNearbyAndRender error", e);
        cards.innerHTML = '<div class="muted">Ошибка при поиске людей</div>';
        countEl.textContent = `Рядом - ?`;
    }
}

function formatDistance(p) {
    const d = Number(p.distance_km);
    if (!isFinite(d) || d <= 0) return "";
    if (d < 1) {
        return `${Math.round(d * 1000)} м`;
    } else if (d < 10) {
        return `${(Math.round(d * 10) / 10).toFixed(1)} км`;
    } else {
        return `${Math.round(d)} км`;
    }
}

// Экспорты
export {
    getCurrentPositionPromise, sleep, randomDelayMs,
    startRadarRings, stopRadarRings,
    showEatHint, hideEatHint,
    getEatCircle, setEatCircleSearching, setEatCircleActive,
    startEatingWithDelay, showEatStatus, hideEatStatus,
    startEating, stopEating, startUpdateLoop, stopUpdateLoop,
    showTimerAndUi, hideTimerAndUi,
    pluralizePeople, fetchNearbyAndRender, formatDistance
};