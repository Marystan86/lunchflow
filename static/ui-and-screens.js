// static/ui-and-screens.js

import {
    API_ROOT, DEFAULT_TAGS, reactions,
    hideShareButton, showShareButton,
    postJson, parseInnerQuery, extractTgWebAppDataFromUrl, buildInitDataObject,
    verifyInitData, saveTgId, getTgId, ensureTgId,
    $qs, escapeHtml
} from './utils.js';

import {
    getCurrentPositionPromise, sleep, randomDelayMs,
    startRadarRings, stopRadarRings,
    showEatHint, hideEatHint,
    getEatCircle, setEatCircleSearching, setEatCircleActive,
    startEatingWithDelay, showEatStatus, hideEatStatus,
    startEating, stopEating, startUpdateLoop, stopUpdateLoop,
    showTimerAndUi, hideTimerAndUi,
    pluralizePeople, fetchNearbyAndRender, formatDistance
} from './geo-and-session.js';

import {loadPlacesIntoHome} from "./places.js";


async function fetchPlacesApi(limit = 10) {
  try {
    const res = await fetch(`/api/places?limit=${limit}`);
    const j = await res.json();
    return j.places || [];
  } catch(e) {
    console.error("fetchPlacesApi", e);
    return [];
  }
}

async function openInviteModal(toTgId) {
    if (!toTgId) return alert("кому позвать не указан");

    const fromTg = getTgId();
    if (!fromTg) { alert("Авторизуйтесь через Telegram, чтобы отправить приглашение."); return; }

    const container = $qs("#screenModals") || (function(){
        const c = document.createElement("div"); c.id = "screenModals"; document.body.appendChild(c); return c;
    })();
    const prev = container.querySelector("#inviteModal");
    if (prev) prev.remove();

    const modal = document.createElement("div");
    modal.id = "inviteModal";
    modal.className = "modal";
    modal.innerHTML = `
      <div class="modal-overlay"></div>
      <div class="modal-window invite-modal" role="dialog" aria-modal="true" aria-labelledby="inviteTitle">
        <h3 id="inviteTitle">Позвать на встречу</h3>

        <label for="inviteTypeSelect" style="display:block;margin-bottom:6px;font-weight:600">Тип встречи</label>
        <div id="inviteType" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;">
          <label><input type="radio" name="meal" value="Завтрак" /> Завтрак</label>
          <label><input type="radio" name="meal" value="Обед" /> Обед</label>
          <label><input type="radio" name="meal" value="Ужин" /> Ужин</label>
          <label><input type="radio" name="meal" value="Попить кофе" /> Попить кофе</label>
        </div>

        <label for="inviteTime" style="display:block;margin-bottom:6px;font-weight:600">Время</label>
        <input id="inviteTime" type="datetime-local" style="width:90%;padding:10px;border-radius:8px;border:1px solid rgba(0,0,0,0.08);margin-bottom:12px;" />

        <label for="invitePlace" style="display:block;margin-bottom:6px;font-weight:600">Место</label>
        <select id="invitePlace" style="width:100%;padding:10px;border-radius:8px;border:1px solid rgba(0,0,0,0.08);margin-bottom:12px;">
          <option value="">- Не указано -</option>
        </select>

        <label for="inviteMessage" style="display:block;margin-bottom:6px;font-weight:600">Сообщение (необязательно)</label>
        <textarea id="inviteMessage" rows="4" style="width:90%;padding:10px;border-radius:8px;border:1px solid rgba(0,0,0,0.08);margin-bottom:12px;" placeholder="Например: Давай выпьем кофе в 16:00 у входа"></textarea>

        <div class="modal-actions" style="display:flex;gap:8px;justify-content:flex-end;">
          <button id="inviteCancel" class="btn">Отмена</button>
          <button id="inviteSend" class="btn primary">Отправить</button>
        </div>
      </div>
    `;
    container.appendChild(modal);

    const overlay = modal.querySelector(".modal-overlay");
    const cancel = modal.querySelector("#inviteCancel");
    const sendBtn = modal.querySelector("#inviteSend");
    const timeInput = modal.querySelector("#inviteTime");
    const mealRadios = modal.querySelectorAll('input[name="meal"]');
    const placeSelect = modal.querySelector("#invitePlace");
    const msgInput = modal.querySelector("#inviteMessage");

    // init defaults
    const defaultDate = getTomorrowAt(13,0);
    timeInput.value = formatDatetimeLocal(defaultDate);
    for (const r of mealRadios) { if (r.value === "Обед") r.checked = true; }

    // load places into select (uses fetchPlacesApi from static/client.js)
    (async () => {
        try {
            const places = await fetchPlacesApi(50);
            // ensure unique and stable order
            places.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p.id !== undefined ? String(p.id) : "";
                opt.dataset.name = p.name || "";
                opt.textContent = `${p.name || 'Без названия'}${p.category ? ' - ' + p.category : ''}`;
                placeSelect.appendChild(opt);
            });
        } catch (e) {
            console.warn("places load failed", e);
        }
    })();

    function close() { try { modal.remove(); } catch(e){} }

    if (overlay) overlay.onclick = close;
    if (cancel) cancel.onclick = close;

    sendBtn.onclick = async () => {
        const timeVal = timeInput ? timeInput.value : null;
        const meal = modal.querySelector("input[name='meal']:checked");
        const mealVal = meal ? meal.value : null;
        const placeId = placeSelect ? placeSelect.value : "";
        const placeName = placeSelect ? (placeSelect.selectedOptions[0]?.dataset?.name || "") : "";
        const message = msgInput ? msgInput.value.trim() : "";

        if (!timeVal) { alert("Выберите время"); return; }
        const rawTime = timeVal;
        const timeIso = rawTime ? new Date(rawTime).toISOString() : null;

        // prepare payload
        const payload = {
            from_tg_id: Number(fromTg),
            to_tg_id: Number(toTgId),
            time_iso: timeIso,
            meal_type: mealVal || null,
            place_id: placeId ? (isNaN(Number(placeId)) ? placeId : Number(placeId)) : null,
            place_name: placeName || null,
            message: message || null
        };
        sendBtn.disabled = true;
        try {
            const resp = await postJson("/api/invite", payload);
            if (resp && resp.ok) {
                alert("Приглашение отправлено");
                close();
            } else {
                throw new Error((resp && resp.error) ? resp.error : "server error");
            }
        } catch (err) {
            console.error("invite send failed", err);
            alert("Ошибка отправки приглашения: " + (err.message || err));
        } finally {
            sendBtn.disabled = false;
        }
    };

    setTimeout(() => { if (timeInput && typeof timeInput.focus === 'function') timeInput.focus(); }, 20);
}


// Получить входящие приглашения от сервера
async function fetchIncomingInvites() {
    const tg = getTgId();
    if (!tg) return [];
    try {
        const res = await fetch(`/api/invites?tg_id=${encodeURIComponent(tg)}`, { cache: "no-store" });
        if (!res.ok) throw new Error("fetch failed " + res.status);
        const data = await res.json();
        return Array.isArray(data.invites) ? data.invites : [];
    } catch (e) {
        console.warn("fetchIncomingInvites failed", e);
        return [];
    }
}

// Показывает модалку с приглашением (для получателя)
function openIncomingInviteModal(inv) {
    if (!inv) return;
    const container = $qs("#screenModals") || (function(){
        const c = document.createElement("div"); c.id = "screenModals"; document.body.appendChild(c); return c;
    })();
    const id = `incomingInvite_${inv.id || String(Math.random()).slice(2)}`;
    
    // удаляем старую с тем же id
    const prev = container.querySelector(`#${id}`);
    if (prev) prev.remove();

    console.log("openIncomingInviteModal payload:", inv);

    const modal = document.createElement("div");
    modal.id = id;
    modal.className = "modal";
    const placeText = inv.place_name ? `"${escapeHtml(inv.place_name)}"` : "не указан";
    const fromName = inv.from_name || (inv.from_tg ? "@" + String(inv.from_tg) : null) || "пользователь";

    let time = "";
    if (inv.time_iso) {
        try {
            const dt = new Date(inv.time_iso);
            // формат: "08:00 25 ноября"
            const hhmm = dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            const day = dt.toLocaleDateString('ru-RU', { day: 'numeric' });
            const month = dt.toLocaleDateString('ru-RU', { month: 'long' });
            time = `${hhmm} ${day} ${month}`;
        } catch(e) {
            time = escapeHtml(inv.time_iso || "");
        }
    }

    // подготовим html-переменные
    const messageBlock = inv.message ? `<div style="margin-top:12px;"><strong>Сообщение:</strong><div style="margin-top:6px;">${escapeHtml(inv.message)}</div></div>` : "";

    // затем в modal.innerHTML включи переменную messageBlock и подставь fromName и time
    modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-window" role="dialog" aria-modal="true">
            <h3>Новое приглашение</h3>
            <div class="muted">У вас новое приглашение в ${placeText} от ${escapeHtml(fromName)} на ${escapeHtml(inv.meal_type || '')} ${escapeHtml(time)}</div>
            ${messageBlock}
            <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
            <button id="invCancel_${id}" class="btn">Закрыть</button>
            <button id="invDecline_${id}" class="btn" style="background:#eee">Отказать</button>
            <button id="invAccept_${id}" class="btn primary">Принять</button>
            </div>
        </div>
    `;

    container.appendChild(modal);
    const overlay = modal.querySelector(".modal-overlay");
    const btnClose = modal.querySelector(`#invCancel_${id}`);
    const btnDecline = modal.querySelector(`#invDecline_${id}`);
    const btnAccept = modal.querySelector(`#invAccept_${id}`);

    function close() { try { modal.remove(); } catch(e){} }

    if (overlay) overlay.onclick = close;
    if (btnClose) btnClose.onclick = close;

    async function respond(action) {
        try {
            const payload = { invite_id: inv.id, responder_tg_id: Number(getTgId()), action: action }; // action: "accept"|"decline"
            const resp = await postJson("/api/invite/respond", payload);
            if (!resp || !resp.ok) throw new Error(resp && resp.error ? resp.error : "server error");
            alert(action === "accept" ? "Вы приняли приглашение" : "Вы отказали");
            close();
        } catch (e) {
            console.error("invite respond failed", e);
            alert("Ошибка: " + (e.message || e));
        }
    }

    btnDecline.onclick = () => respond("decline");
    btnAccept.onclick = () => respond("accept");
}


// ========== Global invites poller ==========
// памяти для уже показанных приглашений (внутри страницы)
const seenInviteIds = new Set();

// Показывать только первый новый invite (true) или все подряд (false)
const SHOW_ONLY_FIRST_INVITE = true;

// Пауза между опросами (ms)
const INVITE_POLL_INTERVAL = 15_000;

let _invitePollTimer = null;
let _invitePollRunning = false;

async function pollIncomingInvitesOnce() {
  if (_invitePollRunning) return;
  _invitePollRunning = true;
  try {
    const tg = getTgId();
    if (!tg) return; // не авторизован - нет смысла
    // если вкладка невидима - не опрашиваем (экономия)
    if (typeof document !== "undefined" && document.hidden) return;

    const invites = await fetchIncomingInvites();
    if (!Array.isArray(invites) || invites.length === 0) return;

    // фильтруем новые
    const newInv = invites.filter(inv => !seenInviteIds.has(Number(inv.id)));
    if (!newInv.length) return;

    // отметим как показанные
    newInv.forEach(inv => seenInviteIds.add(Number(inv.id)));

    // Показ: либо первый, либо все
    if (SHOW_ONLY_FIRST_INVITE) {
        console.log("invite:", newInv[0]);
      openIncomingInviteModal(newInv[0]);
    } else {
      for (const inv of newInv) {
        setTimeout(() => openIncomingInviteModal(inv), 200);
      }
    }
  } catch (e) {
    console.warn("pollIncomingInvitesOnce failed", e);
  } finally {
    _invitePollRunning = false;
  }
}

function startInvitePoll(interval = INVITE_POLL_INTERVAL) {
  stopInvitePoll();
  // стартуем немедленно, затем по таймеру
  pollIncomingInvitesOnce();
  _invitePollTimer = setInterval(pollIncomingInvitesOnce, interval);
}

function stopInvitePoll() {
  if (_invitePollTimer) {
    clearInterval(_invitePollTimer);
    _invitePollTimer = null;
  }
}

// уменьшение частоты при скрытой вкладке / возобновление при видимости
// document.addEventListener("visibilitychange", () => {
//   if (document.hidden) {
//     // при переходе в фон - можно приостановить таймер
//     stopInvitePoll();
//   } else {
//     // при возврате - сразу опросить и рестартовать таймер
//     startInvitePoll();
//   }
// });
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        // при возвращении во вкладку - пробуем подтянуть текущую позицию и пересоздать update loop
        const tg = localStorage.getItem("meeteat_tg_id") || getTgId();
        if (tg) {
            navigator.geolocation.getCurrentPosition(pos => {
                try {
                    postJson("/start", { tg_id: Number(tg), lat: pos.coords.latitude, lon: pos.coords.longitude });
                    fetchNearbyAndRender(Number(tg), pos.coords.latitude, pos.coords.longitude);
                } catch(e){ console.warn("vischg update failed", e); }
            }, err => { console.warn("vischg geo failed", err); }, { enableHighAccuracy: true, maximumAge: 10000 });
            startUpdateLoop(Number(tg));
        }
    } else {
        // вкладка в фоне - можно остановить быстрые обновления, но оставим серверную сессию жить 1 час
        // stopUpdateLoop(); // не обязательно
    }
});








// Рендер карт
function renderPersonCard(p) {
    const art = document.createElement("article");
    art.className = "person-card";
    const avatarSrc = p.avatar || "/static/images/default_avatar.svg";
    const distText = formatDistance(p);
    const ageText = p.age ? (p.age + " лет") : "";
    const metaParts = [];
    if (ageText) metaParts.push(ageText);
    if (distText) metaParts.push(distText);
    art.innerHTML = `
        <img class="avatar" src="${avatarSrc}" alt="${p.name || p.username || 'user'}" />
        <div class="p-info">
            <div class="p-name">${escapeHtml(p.name || (p.username ? '@'+p.username : 'Пользователь'))}</div>
            <div class="p-meta">${metaParts.join(" · ")}</div>
            <div class="p-tags"></div>
        </div>
    `;
    const img = art.querySelector("img");
    if (img) img.onerror = () => { img.src = "/static/images/default_avatar.svg"; };
    art.setAttribute("tabindex", "0");
    art.setAttribute("role", "button");
    art.setAttribute("aria-label", p.name || p.username || "Пользователь");
    // клавиатурная активация (Enter / Space)
    art.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            art.click();
        }
    });
    art.addEventListener("click", () => {
        openUserProfilePage(p.tg_id || p.username);
    });
    return art;
}

function renderInterestCard(u) {
    const art = document.createElement("div");
    art.className = "interest-card";
    const avatarSrc = u.avatar || "/static/images/default_avatar.svg";
    const tagsHtml = (u.tags || []).slice(0,3).map(t => `<span>${escapeHtml(t)}</span>`).join("");
    art.innerHTML = `
        <img class="avatar" src="${avatarSrc}" alt="${u.name || u.username || 'user'}"/>
        <div class="info">
            <div class="name">${escapeHtml(u.name || (u.username ? '@' + u.username : 'Пользователь'))}</div>
            <div class="age">${u.age ? (u.age + " лет") : ""}${(u.common ? (" · " + u.common + " совпад.") : "")}</div>
        </div>
        <div class="tags">${tagsHtml}</div>
    `;
   
    const img = art.querySelector("img");
    if (img) img.onerror = () => { img.src = "/static/images/default_avatar.svg"; };
    art.setAttribute("tabindex", "0");
    art.setAttribute("role", "button");
    art.setAttribute("aria-label", u.name || u.username || "Пользователь");
    // клавиатурная активация (Enter / Space)
    art.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            art.click();
        }
    });
    // по клику открываем профиль/telegram
    art.addEventListener("click", () => {
        openUserProfilePage(u.tg_id || u.username);
    });
    return art;
}

async function fetchSimilarAndRender() {
    const list = $qs("#interestList");
    if (!list) return;
    const placeholder = $qs("#interestListPlaceholder");
    if (placeholder) placeholder.textContent = "Загрузка похожих пользователей…";
    const tg_id = getTgId();
    if (!tg_id) {
        if (placeholder) placeholder.textContent = "Войдите через Telegram, чтобы видеть людей с похожими интересами.";
        return;
    }
    try {
        const res = await fetch(`/api/users/similar?tg_id=${encodeURIComponent(tg_id)}&limit=12`, { cache: "no-store" });
        if (!res.ok) throw new Error("fetch failed " + res.status);
        const data = await res.json();
        if (!data || !data.users || !data.users.length) {
            list.innerHTML = '<div class="muted">Похожих пользователей не найдено</div>';
            return;
        }
        list.innerHTML = "";
        for (const u of data.users) {
            const node = renderInterestCard(u);
            list.appendChild(node);
        }
    } catch (e) {
        console.error("fetchSimilarAndRender error", e);
        list.innerHTML = '<div class="muted">Ошибка при загрузке похожих пользователей</div>';
    }
}

// Отзывы
async function fetchReviewsFor(tg_id, viewer_tg_id = null) {
    const q = new URLSearchParams({ tg_id: String(tg_id) });
    if (viewer_tg_id) q.set("viewer_tg_id", String(viewer_tg_id));
    const res = await fetch(`/api/reviews?${q.toString()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("fetch reviews failed");
    return res.json();
}

function renderRecentReviews(container, recent) {
    container.innerHTML = "";
    for (const r of recent) {
        const el = document.createElement("div");
        el.className = "recent-full";
        el.innerHTML = `
            <img class="mini-avatar" src="${r.reviewer_avatar || '/static/images/default_avatar.svg'}" onerror="this.src='/static/images/default_avatar.svg'"/>
            <div class="rf-body"><div class="rf-name">${escapeHtml(r.reviewer_name || r.reviewer_tg)}</div>
            <div class="rf-meta">${escapeHtml(r.reaction)} · ${escapeHtml(r.created_at)}</div>
            <div class="rf-comment">${escapeHtml(r.comment || '')}</div></div>
        `;
        container.appendChild(el);
    }
}

// Теги модалка
async function fetchAvailableTags(limit = 50) {
    try {
        const res = await fetch(`/api/tags?limit=${encodeURIComponent(limit)}`, { cache: "no-store" });
        if (res.ok) {
            const data = await res.json();
            if (data && Array.isArray(data.tags) && data.tags.length) {
                return data.tags.map(it => ({ tag: String(it.tag || "").toLowerCase(), count: Number(it.count || 0) }));
            }
        }
    } catch (e) {
        console.warn("fetchAvailableTags failed, will use DEFAULT_TAGS", e);
    }
    return DEFAULT_TAGS.map(t => ({ tag: String(t).toLowerCase(), count: 0 }));
}

async function openTagModal(existingTags = [], user = null) {
    const modal = $qs("#tagModal");
    if (!modal) return;
    if (!document.body.contains(modal)) document.body.appendChild(modal);
    const list = $qs("#tagModalList");
    list.innerHTML = "";
    // нормализуем выбранные теги (из caller / сервер)
    const selected = new Set((existingTags || []).map(t => String(t || "").toLowerCase().trim()).filter(Boolean));
    const existingNorm = Array.from(selected); // массив уникальных выбранных
    // Берём популярные теги из DEFAULT_TAGS (без запроса к бэку)
    const availNorm = DEFAULT_TAGS.map(t => String(t).toLowerCase().trim()).filter(Boolean);
    
    // helper для создания кнопки тега
    const createTagButton = (t) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tag" + (selected.has(t) ? " selected" : "");
        btn.dataset.value = t;
        btn.textContent = t[0] ? (t[0].toUpperCase() + t.slice(1)) : t;
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            if (btn.classList.contains("selected")) {
                btn.classList.remove("selected");
                selected.delete(t);
            } else {
                btn.classList.add("selected");
                selected.add(t);
            }
        });
        return btn;
    };

    // 1) отрисуем популярные теги в первой секции
    const popularWrap = document.createElement("div");
    popularWrap.className = "tag-section popular";
    const popTitle = document.createElement("div");
    popTitle.className = "tag-section-title";
    popTitle.textContent = "Популярные";
    popularWrap.appendChild(popTitle);
    for (const t of availNorm) {
        popularWrap.appendChild(createTagButton(t));
    }
    list.appendChild(popularWrap);

    // 2) отрисуем дополнительные пользовательские теги, которых нет в популярных
    const extras = existingNorm.filter(t => !availNorm.includes(t));
    if (extras.length) {
        const yourWrap = document.createElement("div");
        yourWrap.className = "tag-section yours";
        const yourTitle = document.createElement("div");
        yourTitle.className = "tag-section-title";
        yourTitle.textContent = "Ваши теги";
        yourWrap.appendChild(yourTitle);
        for (const t of extras) {
            yourWrap.appendChild(createTagButton(t));
        }
        list.appendChild(yourWrap);
    }
    // 3) если нет ни одного тега (крайний случай) - покажем подсказку
    if (availNorm.length === 0 && extras.length === 0) {
        const hint = document.createElement("div");
        hint.className = "muted";
        hint.textContent = "Нет доступных тегов - добавьте свой.";
        list.appendChild(hint);
    }
    // show modal
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    // focus - делаем после рендера
    setTimeout(() => {
        const first = list.querySelector(".tag") || $qs("#tagModalSave");
        if (first && typeof first.focus === "function") first.focus();
    }, 20);
    // keyboard handlers
    function onKey(e) {
        if (e.key === "Escape") { e.preventDefault(); closeTagModal(); }
        if (e.key === "Enter" && (document.activeElement && document.activeElement.classList.contains("tag"))) {
            document.activeElement.click();
        }
    }
    document.addEventListener("keydown", onKey);
    // click handlers
    const cancel = $qs("#tagModalCancel");
    const save = $qs("#tagModalSave");
    const overlay = modal.querySelector(".modal-overlay");
    const cleanupHandlers = () => {
        document.removeEventListener("keydown", onKey);
        if (cancel) cancel.onclick = null;
        if (save) save.onclick = null;
        if (overlay) overlay.onclick = null;
    };
    const closeAndCleanup = () => { closeTagModal(); cleanupHandlers(); };
    if (cancel) cancel.onclick = closeAndCleanup;
    if (overlay) overlay.onclick = closeAndCleanup;
    save.onclick = async () => {
        const picked = Array.from(list.querySelectorAll(".tag.selected"))
            .map(n => (n.dataset.value || n.textContent || "").toString().trim().toLowerCase().replace(/\s+/g, ' '))
            .filter(Boolean);
        const tg_id = getTgId();
        if (!tg_id) { alert("Авторизуйтесь через Telegram для сохранения"); return; }
        try {
            const resp = await postJson("/api/profile/tags", { tg_id, tags: picked });
            if (!resp || !resp.ok) throw new Error("save failed");
            closeAndCleanup();
            runScreenInit("profile");
        } catch (err) {
            console.error("save tags failed", err);
            alert("Ошибка сохранения: " + (err.message || err));
        }
    };
}

function closeTagModal() {
    const modal = $qs("#tagModal");
    if (!modal) return;
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden","true");
    const list = $qs("#tagModalList");
    if (list) list.innerHTML = "";
}

// Invite модалка
function formatDatetimeLocal(d) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function getTomorrowAt(hour = 12, minute = 0) {
    const now = new Date();
    const t = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, hour, minute, 0, 0);
    return t;
}





function insertAfter(refNode, newNode) {
    if (!refNode || !refNode.parentNode) return;
    refNode.parentNode.insertBefore(newNode, refNode.nextSibling);
}

// Профили
function openUserProfilePage(tg_id) {
    if (!tg_id) {
        alert("tg_id не указан");
        return;
    }
    try {
        sessionStorage.setItem("view_tg_id", String(tg_id));
    } catch (e) {
        console.warn("sessionStorage set failed", e);
    }
    loadScreen("user_profile_view");
}

// Screens
const APP = $qs("#app");
let currentScreen = null;
function sanitizeScreenName(name) {
    if (!name) return "home";
    name = name.split("?")[0].split("#")[0];
    if (name.endsWith(".html")) name = name.slice(0, -5);
    if (name.includes("tgWebAppData=")) return "home";
    name = name.replace(/[^a-z0-9_\-]/gi, "");
    return name || "home";
}

async function loadScreen(name) {
    name = sanitizeScreenName(name);
    if (name === currentScreen) return;
    currentScreen = name;
    const url = `/screens/${name}.html`;
    try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error("fetch failed " + res.status);
        APP.innerHTML = await res.text();
        runScreenInit(name);
        history.pushState({screen: name}, "", `#${name}`);
        document.body.setAttribute("data-screen", name);
        if (typeof window.showFloatingBackBtn === 'function') window.showFloatingBackBtn(name === 'user_profile_view');
    } catch(e) {
        console.error(e);
        APP.innerHTML = `<div class="err">Ошибка загрузки: ${e.message}</div>`;
    }
}

const screenInits = {
    home() {
        const btn = $qs("#startBtn");
        if (btn) btn.addEventListener("click", startEating);
        const stopBtn = $qs("#stopBtn");
        if (stopBtn) stopBtn.addEventListener("click", stopEating);
        fetchSimilarAndRender();
        loadPlacesIntoHome()
    },
    feed() {
        const btn = $qs("#refreshNearby");
        if (btn) btn.addEventListener("click", async () => {
            const tg_id = Number(localStorage.getItem("meeteat_tg_id"));
            const lat = 0, lon = 0;
            try {
                const q = await fetch(`/nearby?tg_id=${tg_id}&lat=${lat}&lon=${lon}`).then(r => r.json());
                console.log("nearby:", q);
            } catch(e) {
                console.error(e);
            }
        });
        const eatCircle = $qs("#eatCircle");
        if (eatCircle) {
            eatCircle.addEventListener("click", async () => {
                const isActive = eatCircle.classList.contains("active");
                if (isActive) {
                    if (confirm("Остановить сессию?")) {
                        await stopEating();
                        showEatHint("Нажми на кнопку, чтобы найти людей рядом");
                    }
                    return;
                }
                startEatingWithDelay();
            });
            eatCircle.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    eatCircle.click();
                }
            });
        }
    },
    map(){},
    chat(){},
    profile: async function() {
        const avatarEl = $qs("#profileAvatar");
        const nameEl = $qs("#profileName");
        const usernameEl = $qs("#profileUsername");
        const ageEl = $qs("#profileAge");
        const geoEl = $qs("#profileGeo");
        const meetList = $qs("#meetList");
        const tagsPanel = $qs("#tagsPanel");
        const settingsBtn = $qs("#profileSettings");
        function setImgWithFallback(imgEl, src) {
            if (!imgEl) return;
            imgEl.onerror = () => { imgEl.src = "/static/images/default_avatar.svg"; };
            imgEl.src = src || "/static/images/default_avatar.svg";
        }
        // reset UI
        if (meetList) meetList.innerHTML = '<div class="muted">Загрузка...</div>';
        if (tagsPanel) {
            const addBtn = tagsPanel.querySelector(".tag.outline") || null;
            tagsPanel.innerHTML = "";
            if (addBtn) tagsPanel.appendChild(addBtn);
        }
        const tg_id = getTgId();
        if (!tg_id) {
            const name = localStorage.getItem("meeteat_name") || "Пользователь";
            const username = localStorage.getItem("meeteat_username") || "";
            const avatar = localStorage.getItem("meeteat_avatar") || "/static/images/default_avatar.svg";
            setImgWithFallback(avatarEl, avatar);
            if (nameEl) nameEl.textContent = name;
            if (usernameEl) usernameEl.textContent = username ? `@${username}` : "";
            if (ageEl) ageEl.textContent = "";
            if (meetList) meetList.innerHTML = '<div class="muted">Контактов не найдено</div>';
            return;
        }
        // settings opens edit screen
        if (settingsBtn) {
            settingsBtn.onclick = () => {
                loadScreen("profile_edit");
            };
        }
        try {
            const res = await fetch(`/api/profile?tg_id=${tg_id}`, { cache: "no-store" }).then(r => r.json());
            if (!res.ok) {
                console.warn("profile fetch failed", res);
                return;
            }
            const u = res.user || {};
            setImgWithFallback(avatarEl, u.avatar);
            if (nameEl) nameEl.textContent = u.name || u.username || "Пользователь";
            if (usernameEl) usernameEl.textContent = u.username ? `@${u.username}` : "";
            if (ageEl) ageEl.textContent = u.age ? `${u.age} лет` : "";
            
            // tags
            const tags = res.tags || [];
            if (tagsPanel) {
                tagsPanel.innerHTML = "";
                for (const t of tags) {
                    const btn = document.createElement("button");
                    btn.className = "tag";
                    btn.textContent = t;
                    tagsPanel.appendChild(btn);
                }
                const add = document.createElement("button");
                add.className = "tag outline";
                add.textContent = "Добавить +";
                add.addEventListener("click", async () => {
                    try {
                        const tg = getTgId();
                        if (!tg) return alert("tg_id не найден");
                        const resp = await fetch(`/api/profile/tags?tg_id=${encodeURIComponent(tg)}`, { cache: "no-store" })
                            .then(r => r.json());
                        const current = (resp && resp.ok && Array.isArray(resp.tags)) ? resp.tags : [];
                        openTagModal(current, null);
                    } catch (e) {
                        console.warn("profile fetch failed for modal", e);
                        openTagModal([], null);
                    }
                });
                tagsPanel.appendChild(add);
            }

            try {
                // удалим старый блок если он есть
                const oldMatch = $qs("#profileMatchCount");
                if (oldMatch) oldMatch.remove();
                const oldInterestsTitle = $qs("#profileInterestsTitle");
                if (oldInterestsTitle) oldInterestsTitle.remove();
                const oldReviewsTitle = $qs("#profileReviewsTitle");
                if (oldReviewsTitle) oldReviewsTitle.remove();
                const prev = $qs("#profileReviewsSummary");
                if (prev) prev.remove();


                // заголовок для интересов
                const interestsTitle = document.createElement("h3");
                interestsTitle.id = "profileInterestsTitle";
                interestsTitle.textContent = "Мои интересы";
                interestsTitle.className = "section-title";

                // заголовок для отзывов
                const reviewsTitle = document.createElement("h3");
                reviewsTitle.id = "profileReviewsTitle";
                reviewsTitle.textContent = "Мои отзывы";
                reviewsTitle.className = "section-title";

                // блок для метчингов
                const matchEl = document.createElement("h3");
                matchEl.id = "profileMatchCount";
                matchEl.className = "section-title match-count";
                matchEl.style.cssText = "display:flex;align-items:center;gap:12px;margin:10px 0;font-weight:700;";
                
                let matchCount = 0;
                try {
                    matchCount = Number(res.match_count ?? res.matches_count ?? res.matchings_count ?? 0);
                    if (!matchCount && Array.isArray(res.matches)) matchCount = res.matches.length;
                    if (!matchCount && Array.isArray(res.matchings)) matchCount = res.matchings.length;
                    if (!Number.isFinite(matchCount)) matchCount = 0;
                } catch (e) {
                    matchCount = 0;
                }

                const lbl = document.createElement("span");
                lbl.textContent = "Количество метчингов:";
                lbl.style.cssText = "font-weight:700; font-size:21px; margin-left:3px";
                const num = document.createElement("span");
                num.className = "match-number";
                num.textContent = String(matchCount);
                num.setAttribute("aria-hidden", "true");
                num.style.cssText = "font-weight:700; font-size:21px;";
                matchEl.appendChild(lbl);
                matchEl.appendChild(num);

                // блок для аггрегации отзывов
                const reviewsSummary = document.createElement("div");
                reviewsSummary.id = "profileReviewsSummary";
                reviewsSummary.className = "reviews-summary";

                // вставляем в правильном порядке: сначала метчинги, затем "Мои интересы" и теги, потом отзывы
                if (tagsPanel && tagsPanel.parentNode) {
                    const parent = tagsPanel.parentNode;
                    parent.insertBefore(matchEl, tagsPanel);
                    insertAfter(matchEl, interestsTitle);
                    insertAfter(interestsTitle, tagsPanel);
                    insertAfter(tagsPanel, reviewsTitle);
                    insertAfter(reviewsTitle, reviewsSummary);
                } else {
                    const card = $qs(".profile-card");
                    if (card) {
                        card.appendChild(matchEl);
                        card.appendChild(interestsTitle);
                        if (tagsPanel) card.appendChild(tagsPanel);
                        card.appendChild(reviewsTitle);
                        card.appendChild(reviewsSummary);
                    }
                }

                // отрисовка read-only реакций
                function renderReadOnlyReactions(container, data = {counts:{}}) {
                    container.innerHTML = "";
                    const wrap = document.createElement("div");
                    wrap.className = "reactions-wrap readonly";
                    for (const r of reactions) {
                        const lbl = r.label;
                        const cnt = Number((data.counts && data.counts[lbl]) ? data.counts[lbl] : 0);
                        const node = document.createElement("div");
                        node.className = "reaction-item readonly";
                        node.dataset.reaction = lbl;
                        node.setAttribute("aria-hidden", "false");
                        node.innerHTML = `
                            <div class="reaction-emoji" aria-hidden="true">${r.emoji}</div>
                            <div class="reaction-label">${escapeHtml(lbl)}</div>
                            <span class="reaction-badge" aria-hidden="true">${cnt}</span>
                        `;
                        wrap.appendChild(node);
                    }
                    container.appendChild(wrap);
                }

                // загрузим агрегаты (counts) для текущего профиля
                (async () => {
                    try {
                        const data = await fetchReviewsFor(tg_id);
                        renderReadOnlyReactions(reviewsSummary, data);
                    } catch (err) {
                        console.warn("load profile reviews failed", err);
                        reviewsSummary.innerHTML = '<div class="muted">Не удалось загрузить отзывы</div>';
                    }
                })();
            } catch(e) {
                console.warn("profile reviews insert failed", e);
            }

            // recent contacts (unchanged)
            if (meetList) {
                meetList.innerHTML = "";
                const contacts = res.recent_contacts || [];
                if (!contacts.length) meetList.innerHTML = '<div class="muted">Контактов не найдено</div>';
                else {
                    for (const c of contacts) {
                        const art = document.createElement("article");
                        art.className = "meet-card";
                        const avatar = c.avatar || "/static/images/default_avatar.svg";
                        const lastSeen = c.last_seen ? c.last_seen.split("T")[0] : "";
                        art.innerHTML = `
                        <img class="meet-avatar" src="${avatar}" alt="${c.name || c.username || 'user'}"/>
                        <div class="meet-info">
                            <div class="meet-name">${c.name || ('@' + (c.username || ''))}</div>
                            <div class="meet-place">${c.username ? '@' + c.username : ''}${c.age ? ' · ' + c.age + ' лет' : ''}</div>
                            <div class="meet-date">${lastSeen}</div>
                        </div>
                        `;
                        const img = art.querySelector("img");
                        if (img) img.onerror = () => { img.src = "/static/images/default_avatar.svg"; };
                        meetList.appendChild(art);
                    }
                }
            }
        } catch (e) {
            console.error("profile load error", e);
        }
    },
    profile_edit: async function() {
        const tg_id = getTgId();
        if (!tg_id) {
            alert("tg_id не найден. Авторизуйтесь через Telegram.");
            loadScreen("home");
            return;
        }
        const nameInput = $qs("#editName");
        const usernameInput = $qs("#editUsername");
        const ageInput = $qs("#editAge");
        const avatarInput = $qs("#editAvatar");
        const avatarPreview = $qs("#editAvatarPreview");
        const saveBtn = $qs("#saveProfileBtn");
        const cancelBtn = $qs("#cancelEditBtn");
        function setImgWithFallback(imgEl, src) {
            if (!imgEl) return;
            imgEl.onerror = () => { imgEl.src = "/static/images/default_avatar.svg"; };
            imgEl.src = src || "/static/images/default_avatar.svg";
        }
        try {
            const resp = await fetch(`/api/profile?tg_id=${encodeURIComponent(tg_id)}`, { cache: "no-store" });
            if (!resp.ok) {
                console.warn("profile fetch http failed", resp.status, resp.statusText);
                alert("Не удалось загрузить профиль (сервер вернул ошибку)");
                loadScreen("profile");
                return;
            }
            const res = await resp.json();
            const u = res.user || {};
            if (nameInput) nameInput.value = u.name || "";
            if (usernameInput) usernameInput.value = u.username || "";
            if (ageInput) ageInput.value = u.age ? String(u.age) : "";
            if (avatarInput) avatarInput.value = u.avatar || "";
            setImgWithFallback(avatarPreview, u.avatar);
            // preview avatar on input change
            if (avatarInput) avatarInput.addEventListener("input", () => setImgWithFallback(avatarPreview, avatarInput.value));
            // cancel
            if (cancelBtn) cancelBtn.onclick = () => loadScreen("profile");
            // save - только профиль (без тегов)
            if (saveBtn) saveBtn.onclick = async () => {
                const newName = nameInput ? nameInput.value.trim() || null : null;
                const newUsername = usernameInput ? usernameInput.value.trim() || null : null;
                const newAgeVal = ageInput && ageInput.value ? Number(ageInput.value) : null;
                const newAvatar = avatarInput ? avatarInput.value.trim() || null : null;
                const updatePayload = { tg_id };
                if (newName !== null) updatePayload.name = newName;
                if (newAvatar) updatePayload.avatar = newAvatar;
                if (newAgeVal !== null && !Number.isNaN(newAgeVal)) updatePayload.age = newAgeVal;
                if (newUsername !== null) updatePayload.username = newUsername;
                try {
                    const upd = await postJson("/api/profile/update", updatePayload);
                    if (!upd || !upd.ok) throw new Error("update failed");
                    alert("Профиль сохранён");
                    // update local cache
                    if (newName) localStorage.setItem("meeteat_name", newName);
                    if (newUsername) localStorage.setItem("meeteat_username", newUsername);
                    if (newAvatar) localStorage.setItem("meeteat_avatar", newAvatar);
                    loadScreen("profile");
                } catch (e) {
                    console.error(e);
                    alert("Ошибка при сохранении: " + (e.message || e));
                }
            };
        } catch (e) {
            console.error("profile_edit load error", e);
            alert("Ошибка загрузки профиля");
            loadScreen("profile");
        }
    },
};
screenInits.user_profile_view = async function() {
    const backBtn = $qs("#backBtn");
    if (backBtn) backBtn.onclick = () => { window.history.back(); };
    const viewAvatar = $qs("#viewAvatar");
    const viewName = $qs("#viewName");
    const viewUsername = $qs("#viewUsername");
    const viewAge = $qs("#viewAge");
    const reviewsList = $qs("#reviewsList");
    const callBtn = $qs("#callBtn");

    // get tg_id from sessionStorage
    const viewTg = sessionStorage.getItem("view_tg_id");
    if (!viewTg) {
        if (viewName) viewName.textContent = "Пользователь не найден";
        if (reviewsList) reviewsList.innerHTML = '<div class="muted">Невозможно загрузить профиль</div>';
        return;
    }

    // загрузим профиль целевого пользователя (если у вас API /api/profile?tg_id=... - используем его)
    try {
        const res = await fetch(`/api/profile?tg_id=${encodeURIComponent(viewTg)}`, { cache: "no-store" });
        const data = await res.json();
        if (!data || !data.ok) throw new Error("profile fetch failed");
        const u = data.user || {};
        if (viewAvatar) { viewAvatar.onerror = () => { viewAvatar.src = "/static/images/default_avatar.svg"; }; viewAvatar.src = u.avatar || "/static/images/default_avatar.svg"; }
        if (viewName) viewName.textContent = u.name || (u.username ? "@" + u.username : "Пользователь");
        // if (viewUsername) viewUsername.textContent = u.username ? `@${u.username}` : "";
        if (viewAge) viewAge.textContent = u.age ? `${u.age} лет` : "";
        
        // Добавляем заголовок "Интересы"
        const interestsTitle = document.createElement("h3");
        interestsTitle.textContent = "Интересы";
        interestsTitle.className = "section-title";

        // render tags for viewed profile
        const viewTagsPanel = document.createElement("div");
        viewTagsPanel.className = "tags-panel";
        viewTagsPanel.id = "viewTagsPanel";
        if ((data.tags || []).length === 0) {
            viewTagsPanel.innerHTML = '<div class="muted">Интересы не указаны</div>';
        } else {
            for (const t of data.tags) {
                const btn = document.createElement("button");
                btn.className = "tag";
                btn.textContent = t;
                viewTagsPanel.appendChild(btn);
            }
        }

        // insert tagsPanel right after profile-top (before reviews)
        const profileCard = $qs(".profile-card");
        const topNode = profileCard ? profileCard.querySelector(".profile-top") : null;
        const matchElView = document.createElement("h3");
        matchElView.className = "section-title view-match";
        matchElView.style.cssText = "display:flex;align-items:center;gap:12px;margin:10px 5px;font-weight:700;font-siza: 21px;";
        const lblView = document.createElement("span");
        lblView.textContent = "Количество метчингов:";
        lblView.style.cssText = "font-weight:700; font-size:21px;";
        const numView = document.createElement("span");
        numView.className = "match-number";
        numView.textContent = "0";
        numView.setAttribute("aria-hidden", "true");
        numView.style.cssText = "font-weight:700; font-size:21px;";
        matchElView.appendChild(lblView);
        matchElView.appendChild(numView);
        if (profileCard) {
            if (topNode && topNode.nextSibling) {
                profileCard.insertBefore(matchElView, topNode.nextSibling); // match first
                insertAfter(matchElView, interestsTitle);                  // then interests title
                insertAfter(interestsTitle, viewTagsPanel);                // then tags panel
            } else {
                profileCard.appendChild(matchElView);
                profileCard.appendChild(interestsTitle);
                profileCard.appendChild(viewTagsPanel);
            }
        }
    } catch (e) {
        console.error("load profile view error", e);
        if (viewName) viewName.textContent = "Ошибка загрузки профиля";
    }
    
    // --- replace existing interactive reviewsList block in user_profile_view with this read-only renderer ---
    if (reviewsList) {
        reviewsList.innerHTML = "";
        const summaryWrap = document.createElement("div");
        summaryWrap.className = "reviews-summary";

        // render read-only reactions (same look as profile)
        function renderReadOnlyReactionsTo(container, data = {counts:{}}) {
            container.innerHTML = "";
            const wrap = document.createElement("div");
            wrap.className = "reactions-wrap readonly";
            for (const r of reactions) {
                const lbl = r.label;
                const cnt = Number((data.counts && data.counts[lbl]) ? data.counts[lbl] : 0);
                const node = document.createElement("div");
                node.className = "reaction-item readonly";
                node.dataset.reaction = lbl;
                node.setAttribute("aria-hidden", "false");
                node.innerHTML = `
                    <div class="reaction-emoji" aria-hidden="true">${r.emoji}</div>
                    <div class="reaction-label">${escapeHtml(lbl)}</div>
                    <span class="reaction-badge" aria-hidden="true">${cnt}</span>
                `;
                wrap.appendChild(node);
            }
            container.appendChild(wrap);
        }

        // initial load: fetch aggregates (counts) for viewed profile and render
        (async () => {
            try {
                const tgt = sessionStorage.getItem("view_tg_id");
                if (!tgt) {
                    summaryWrap.innerHTML = '<div class="muted">Невозможно загрузить отзывы</div>';
                } else {
                    const data = await fetchReviewsFor(tgt); // read-only, no viewer passed
                    renderReadOnlyReactionsTo(summaryWrap, data);
                }
            } catch (e) {
                console.warn("load read-only reviews failed", e);
                summaryWrap.innerHTML = '<div class="muted">Не удалось загрузить отзывы</div>';
            }
        })();

        reviewsList.appendChild(summaryWrap);
    }

    // Позвать - открывает модалку
    if (callBtn) {
        callBtn.onclick = () => openInviteModal(viewTg);
    }
};

function runScreenInit(name) {
    (screenInits[name] || (() => {}))();
}

// Инициализация
async function tryAutoStart() {
    const tg_id = await ensureTgId();
    if (!tg_id) return;

    // try get geolocation silently
    navigator.geolocation.getCurrentPosition(async pos => {
        try {
            const body = { tg_id, lat: pos.coords.latitude, lon: pos.coords.longitude };
            const data = await postJson("/start", body);
            console.log("auto-start:", data);
            showEatStatus(data.expires_at);
            showTimerAndUi(data.expires_at);
            startUpdateLoop(tg_id);
        } catch (e) {
            console.warn("auto start failed", e);
        }
    }, (err) => {
        console.warn("geo denied or failed", err);
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 });
}

// ========== Notifications for initiator (mini-app) ==========
let _notifPollTimer = null;
const NOTIF_POLL_INTERVAL = 15_000;
const seenNotifIds = new Set();

async function fetchNotifications() {
    const tg = getTgId();
    if (!tg) return [];
    try {
        const res = await fetch(`/api/notifications?tg_id=${encodeURIComponent(tg)}`, { cache: "no-store" });
        if (!res.ok) return [];
        const j = await res.json();
        return Array.isArray(j.notifications) ? j.notifications : [];
    } catch (e) {
        console.warn("fetchNotifications failed", e);
        return [];
    }
}

function safePayload(notif) {
    let pl = notif && notif.payload ? notif.payload : {};
    if (typeof pl === 'string') {
        try { pl = JSON.parse(pl); } catch(e) { console.warn("safePayload: payload parse failed", e, pl); pl = {raw: pl}; }
    }
    return pl;
}


function openNotificationModal(notif) {
    if (!notif) return;

    const payload = safePayload(notif);
    console.log("[openNotificationModal] decoded payload:", payload);

    
    const container = $qs("#screenModals") || (function(){ const c = document.createElement("div"); c.id = "screenModals"; document.body.appendChild(c); return c; })();
    const id = `notif_${notif.id}_${String(Math.random()).slice(2)}`;
    const prev = container.querySelector('#' + id);
    if (prev) prev.remove();

    const modal = document.createElement("div");
    modal.id = id;
    modal.className = "modal";
    // survey
    if (notif.type === "survey") {
        const partner = payload.partner_name || "партнёр";
        const place = payload.place_name || "";
        modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-window" role="dialog" aria-modal="true">
            <h3>Опрос по встрече</h3>
            <div class="muted">Сходили ли вы с "${escapeHtml(partner)}" ${place ? 'в "' + escapeHtml(place) + '"' : ''}?</div>
            <div style="display:flex;gap:8px;margin-top:12px;">
            <button id="${id}_yes" class="btn primary">Да</button>
            <button id="${id}_no" class="btn">Нет</button>
            </div>
        </div>
        `;
        container.appendChild(modal);
        modal.querySelector(".modal-overlay").onclick = () => modal.remove();

        const doRespond = async (ans) => {
        const tg = getTgId();
        if (!tg) return alert("Войдите через Telegram");
        try {
            const resp = await postJson("/api/survey/respond", { invite_id: payload.invite_id, tg_id: tg, answer: ans });
            if (!resp || !resp.ok) {
            alert("Ошибка: " + (resp && resp.error ? resp.error : "server error"));
            return;
            }
            modal.remove();
        } catch (e) {
            console.error(e);
            alert("Ошибка отправки ответа");
        }
        };

        modal.querySelector("#" + id + "_yes").onclick = () => doRespond("yes");
        modal.querySelector("#" + id + "_no").onclick = () => doRespond("no");
        return;
    }

    // survey followup (prompt to leave review)
    if (notif.type === "survey_followup") {
        const partner = payload.partner_name || "пользователь";
        const prompt = payload.prompt || `Оставьте отзыв об ${partner} в нашем мини-аппе`;
        const reactions = payload.reactions || [];
        modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-window" role="dialog" aria-modal="true">
            <h3>Отзыв</h3>
            <div class="muted">${escapeHtml(prompt)}</div>
            <div id="${id}_reactions" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;"></div>
        </div>
        `;
        container.appendChild(modal);
        modal.querySelector(".modal-overlay").onclick = () => modal.remove();
        const wrap = modal.querySelector("#" + id + "_reactions");
        reactions.forEach(r => {
        const b = document.createElement("button");
        b.className = "btn";
        b.textContent = r;
        b.onclick = async () => {
            const tg = getTgId();
            if (!tg) return alert("Войдите через Telegram");
            try {
            const res = await postJson("/api/review/toggle", { reviewer_tg_id: tg, target_tg_id: (payload.partner_tg || payload.partner_tg_id), reaction: r });
            if (!res || !res.ok) {
                alert("Ошибка");
                return;
            }
            alert("Спасибо - отзыв сохранён");
            modal.remove();
            } catch (e) {
            console.error(e);
            alert("Ошибка отправки отзыва");
            }
        };
        wrap.appendChild(b);
        });
        return;
    }

    // survey_negative
    if (notif.type === "survey_negative") {
        const msg = (notif.payload && notif.payload.message) || "Ничего страшного - найдете другого.";
        modal.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-window"><h3>Опрос</h3><div class="muted">${escapeHtml(msg)}</div><div style="display:flex;justify-content:flex-end;margin-top:12px;"><button class="btn" id="${id}_close">Закрыть</button></div></div>
        `;
        container.appendChild(modal);
        modal.querySelector(".modal-overlay").onclick = () => modal.remove();
        modal.querySelector("#" + id + "_close").onclick = () => modal.remove();
        return;
    }


    const p = notif.payload || {};
    const placeText = p.place_name ? `"${escapeHtml(p.place_name)}"` : "не указан";
    const meal = escapeHtml(p.meal_type || "");
    const when = escapeHtml(p.time_readable || "");
    const respName = escapeHtml(p.responder_name || "");
    const status = p.status === "accepted" ? "принято" : "отказано";
    const emojis = p.status === "accepted" ? "🥳🥳🥳" : "😭😭😭";

    // const container = $qs("#screenModals") || (function(){
    //     const c = document.createElement("div"); c.id = "screenModals"; document.body.appendChild(c); return c;
    // })();
    // const id = `notif_${notif.id}_${String(Math.random()).slice(2)}`;
    // const prev = container.querySelector(`#${id}`);
    // if (prev) prev.remove();

    // const modal = document.createElement("div");
    modal.id = id;
    modal.className = "modal";
    modal.innerHTML = `
      <div class="modal-overlay"></div>
      <div class="modal-window" role="dialog" aria-modal="true">
        <h3>Обновление по приглашению</h3>
        <div class="muted">Ваше приглашение ${placeText} с ${respName} на ${meal} ${when} было <strong>${status}</strong> ${emojis}</div>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
          <button id="notifClose_${id}" class="btn">Закрыть</button>
        </div>
      </div>
    `;
    container.appendChild(modal);
    const closeBtn = modal.querySelector(`#notifClose_${id}`);
    const overlay = modal.querySelector(".modal-overlay");
    function close() { try { modal.remove(); } catch(e){} }
    if (overlay) overlay.onclick = close;
    if (closeBtn) closeBtn.onclick = close;
}

async function pollNotificationsOnce() {
    console.log("[pollNotificationsOnce] start; tg=", getTgId && getTgId());

    try {
        const notifs = await fetchNotifications();
        if (!Array.isArray(notifs) || notifs.length === 0) return;
        console.log("[pollNotificationsOnce] got notifs:", notifs);


        // Игнорируем те, что уже прочитаны на сервере, и те, что уже показаны в этой сессии
        const unread = notifs.filter(n => !n.read && !seenNotifIds.has(n.id));
        if (!unread.length) return;

        // Показываем новые (старые сначала)
        for (const n of unread.reverse()) {
            seenNotifIds.add(n.id);
            openNotificationModal(n);

            // Пометить как прочитанное (best-effort)
            try {
                const tg = getTgId();
                if (tg) await postJson("/api/notifications/mark_read", { tg_id: tg, notification_id: n.id });
            } catch (e) {
                console.warn("mark_read failed for", n.id, e);
            }
        }
    } catch (e) {
        console.warn("pollNotificationsOnce failed", e);
    }
}


function startNotificationsPoll(interval = NOTIF_POLL_INTERVAL) {
    if (_notifPollTimer) clearInterval(_notifPollTimer);
    pollNotificationsOnce();
    _notifPollTimer = setInterval(pollNotificationsOnce, interval);
}

function stopNotificationsPoll() {
    if (_notifPollTimer) {
        clearInterval(_notifPollTimer);
        _notifPollTimer = null;
    }
}


document.addEventListener("DOMContentLoaded", async () => {
    const tg = window.Telegram?.WebApp;
    if (tg) try { tg.expand(); } catch(e) {}

    try {
        const rawInit = window.Telegram?.WebApp?.initData ?? null;
        const initData = rawInit ? rawInit : buildInitDataObject();
        if (initData) {
            const resp = await verifyInitData(initData);
            if (resp && resp.ok && resp.tg_id) {
                saveTgId(resp.tg_id);
                if (resp.name) localStorage.setItem("meeteat_name", resp.name);
                if (resp.username) localStorage.setItem("meeteat_username", resp.username);
                if (resp.avatar) localStorage.setItem("meeteat_avatar", resp.avatar);
                showShareButton();
            } else {
                console.warn("verifyInitData failed", resp);
            }
        }
    } catch (e) {
        console.error("verifyInitData error", e);
    }
    startInvitePoll();
    startNotificationsPoll();

    // --- floating back button (top-left) ---
    (function ensureFloatingBackBtn(){
        if ($qs("#floatingBackBtn")) return;
        const btn = document.createElement("button");
        btn.id = "floatingBackBtn";
        btn.type = "button";
        btn.setAttribute("aria-label", "Назад");
        btn.title = "Назад";
        btn.style.display = "none";
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 18L9 12L15 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        // single click handler (history.back with fallback)
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            if (window.history && window.history.length > 1) window.history.back();
            else loadScreen("home");
        });
        // keyboard accessible
        btn.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); btn.click(); }
        });
        document.body.appendChild(btn);
        window.showFloatingBackBtn = function(show) {
            try { btn.style.display = show ? "inline-flex" : "none"; } catch (e) {}
        };
    })();
    const menu = $qs("#menu");
    if (menu) {
        menu.addEventListener("click", (e) => {
            const b = e.target.closest("button[data-screen]");
            if(!b) return;
            loadScreen(b.dataset.screen);
        });
    }
    const initial = location.hash?.slice(1) || "home";
    loadScreen(initial);
});
window.addEventListener("popstate", (e) => {
    const s = (e.state && e.state.screen) || "home";
    loadScreen(s);
});

// --- START: base modals creation + helpers (paste into ui-and-screens.js) ---

// Создаёт статические модалки, если их нет (альтернатива вставке HTML в шаблон)
function ensureBaseModals() {
  if (!$qs("#screenModals")) {
    const c = document.createElement("div"); c.id = "screenModals"; document.body.appendChild(c);
  }
  const container = $qs("#screenModals");

  // tagModal skeleton
  if (!container.querySelector("#tagModal")) {
    container.insertAdjacentHTML("beforeend", `
      <div id="tagModal" class="modal hidden" aria-hidden="true">
        <div class="modal-overlay"></div>
        <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="tagModalTitle">
          <div class="modal-header">
            <div><div class="m-title" id="tagModalTitle">Теги</div><div class="m-sub">Выберите теги или добавьте собственный</div></div>
          </div>
          <div class="modal-body" style="flex-direction:column;gap:12px">
            <div id="tagModalList" class="tag-list" style="max-height:40vh;overflow:auto;padding:6px 0"></div>
            <div style="display:flex;gap:8px;align-items:center;margin-top:6px;">
              <input id="tagModalNewInput" type="text" placeholder="Добавить тег" style="flex:1;padding:8px;border-radius:8px;border:1px solid rgba(0,0,0,0.08)" />
              <button id="tagModalAdd" class="btn">Добавить</button>
            </div>
          </div>
          <div class="modal-actions">
            <button id="tagModalCancel" class="btn outline">Отмена</button>
            <button id="tagModalSave" class="btn primary">Сохранить</button>
          </div>
        </div>
      </div>
    `);
  }

  // reviewModal skeleton
  if (!container.querySelector("#reviewModal")) {
    container.insertAdjacentHTML("beforeend", `
      <div id="reviewModal" class="modal hidden" aria-hidden="true">
        <div class="modal-overlay"></div>
        <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="reviewModalTitle">
          <div class="modal-header">
            <img id="reviewTargetAvatar" class="m-avatar" src="/static/images/default_avatar.svg" alt="" />
            <div><div class="m-title" id="reviewModalTitle">Оставить отзыв</div><div class="m-sub" id="reviewTargetName">Пользователь</div></div>
          </div>
          <div class="modal-body" style="flex-direction:column;gap:12px">
            <div id="reviewReactions" class="reactions-wrap"></div>
            <textarea id="reviewComment" rows="3" placeholder="Комментарий (необязательно)" style="width:100%;padding:8px;border-radius:8px;border:1px solid rgba(0,0,0,0.08)"></textarea>
          </div>
          <div class="modal-actions">
            <button id="reviewModalCancel" class="btn outline">Отмена</button>
            <button id="reviewModalSend" class="btn primary">Отправить</button>
          </div>
        </div>
      </div>
    `);
  }

  // простая логика add/cancel для tagModal (если openTagModal будет использован, он перезапишет list)
  const tagAdd = $qs("#tagModalAdd");
  if (tagAdd && !tagAdd._bound) {
    tagAdd._bound = true;
    tagAdd.addEventListener("click", (e) => {
      e.preventDefault();
      const input = $qs("#tagModalNewInput");
      const val = input && input.value.trim();
      if (!val) return input.focus();
      const normalized = String(val).toLowerCase().replace(/\s+/g, ' ').slice(0,64);
      // если такой уже есть - пометить/выделить
      const existing = Array.from($qs("#tagModalList").querySelectorAll(".tag")).find(n => (n.dataset.value||"") === normalized);
      if (existing) {
        existing.classList.add("selected");
      } else {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tag selected";
        btn.dataset.value = normalized;
        btn.textContent = normalized[0].toUpperCase() + normalized.slice(1);
        btn.addEventListener("click", (ev) => {
          ev.preventDefault();
          btn.classList.toggle("selected");
        });
        $qs("#tagModalList").appendChild(btn);
      }
      input.value = "";
      input.focus();
    });
  }

  // cancel handler for tagModal
  const tagCancel = $qs("#tagModalCancel");
  if (tagCancel && !tagCancel._bound) {
    tagCancel._bound = true;
    tagCancel.addEventListener("click", (e) => {
      e.preventDefault();
      const m = $qs("#tagModal");
      if (m) { m.classList.add("hidden"); m.setAttribute("aria-hidden", "true"); }
    });
    const overlay = $qs("#tagModal .modal-overlay");
    if (overlay) overlay.addEventListener("click", () => { const m = $qs("#tagModal"); if (m) { m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }});
  }

  // review modal handlers
  const revCancel = $qs("#reviewModalCancel");
  if (revCancel && !revCancel._bound) {
    revCancel._bound = true;
    revCancel.addEventListener("click", (e) => {
      e.preventDefault(); const m = $qs("#reviewModal"); if (m) { m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }
    });
    const overlay = $qs("#reviewModal .modal-overlay");
    if (overlay) overlay.addEventListener("click", () => { const m = $qs("#reviewModal"); if (m) { m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }});
  }
}

// Открывает review modal (универсальный): targetTg - tg_id цели, partnerName - имя, partnerAvatar - url
async function openReviewModal(targetTg, partnerName = "Пользователь", partnerAvatar = "/static/images/default_avatar.svg", reactionsList = reactions) {
  ensureBaseModals();
  const m = $qs("#reviewModal");
  if (!m) return alert("review modal not found");
  $qs("#reviewTargetName").textContent = partnerName;
  $qs("#reviewTargetAvatar").src = partnerAvatar || "/static/images/default_avatar.svg";
  const wrap = $qs("#reviewReactions");
  wrap.innerHTML = "";
  let selected = null;

  // render reactions (use provided reactionsList: array of {label, emoji} or strings)
  for (const r of reactionsList) {
    const label = (typeof r === "string") ? r : (r.label || String(r));
    const emoji = (typeof r === "object" && r.emoji) ? r.emoji : "";
    const item = document.createElement("div");
    item.className = "reaction-item";
    item.dataset.reaction = label;
    item.innerHTML = `<div class="reaction-emoji">${emoji}</div><div class="reaction-label">${escapeHtml(label)}</div>`;
    item.addEventListener("click", () => {
      // single select
      selected = label;
      Array.from(wrap.querySelectorAll(".reaction-item")).forEach(n => n.classList.toggle("selected", n === item));
    });
    wrap.appendChild(item);
  }

  // send handler
  const sendBtn = $qs("#reviewModalSend");
  sendBtn.onclick = async () => {
    const tg = getTgId();
    if (!tg) return alert("Войдите через Telegram");
    if (!selected) return alert("Выберите реакцию");
    try {
      sendBtn.disabled = true;
      const resp = await postJson("/api/review/toggle", { reviewer_tg_id: tg, target_tg_id: targetTg, reaction: selected });
      if (!resp || !resp.ok) throw new Error((resp && resp.error) ? resp.error : "server error");
      alert("Спасибо - отзыв сохранён");
      const modal = $qs("#reviewModal");
      if (modal) { modal.classList.add("hidden"); modal.setAttribute("aria-hidden","true"); }
    } catch (e) {
      console.error("review send failed", e);
      alert("Ошибка отправки отзыва: " + (e.message || e));
    } finally {
      sendBtn.disabled = false;
    }
  };

  // show
  m.classList.remove("hidden");
  m.setAttribute("aria-hidden","false");
  setTimeout(() => { const first = wrap.querySelector(".reaction-item"); if (first) first.focus(); }, 20);
}

// Вызови ensureBaseModals() при инициализации страницы
document.addEventListener("DOMContentLoaded", () => {
  try { ensureBaseModals(); } catch (e) { console.warn("ensureBaseModals failed", e); }
});

// --- END: base modals creation + helpers ---

export {
    renderPersonCard, renderInterestCard, fetchSimilarAndRender,
    fetchReviewsFor, renderRecentReviews,
    fetchAvailableTags, openTagModal, closeTagModal,
    formatDatetimeLocal, getTomorrowAt, openInviteModal, insertAfter,
    openUserProfilePage, loadScreen, runScreenInit,
    tryAutoStart
};