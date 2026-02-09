// static/places.js

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

// Рендер карточки: название, категория, рейтинг, время
function renderPlaceCardForHome(place){
  const el = document.createElement('article');
  el.className = 'place-card place-card--simple';
  // сохраним id для удобства
  if (place.id !== undefined) el.dataset.id = String(place.id);

  const name = escapeHtml(place.name || 'Без названия');
  const category = escapeHtml(place.category || '');
  const rating = (place.rating !== undefined && place.rating !== null) ? Number(place.rating) : 0;
  const openTime = escapeHtml(place.open_time || '');
  const closeTime = escapeHtml(place.close_time || '');

  el.innerHTML = `
    <div class="place-info">
      <h5 class="place-name">${name}</h5>
      ${ category ? `<div class="place-category small-muted">${category}</div>` : '' }
      <div class="place-rating">${renderStarsInline(rating)}</div>
      <div class="place-times small-muted">${openTime || closeTime ? (openTime + (openTime && closeTime ? ' - ' : '') + closeTime) : ''}</div>
    </div>
    ${ place.photo ? `<div class="place-thumb"><img src="${escapeAttr(place.photo)}" alt="${escapeAttr(place.name||'')}" /></div>` : '' }
  `;

  // при клике открываем модалку с полными данными (замыкание хранит place)
  el.style.cursor = 'pointer';
  el.addEventListener('click', (e) => {
    // если клик был по ссылке или кнопке внутри карточки - можно обработать отдельно
    showPlaceModal(place);
  });

  return el;
}

// Модалка: показывает все поля заведения, и кнопку закрыть
function showPlaceModal(place){
  // предотвратить дублирование модалки
  if(document.getElementById('placeModalOverlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'placeModalOverlay';
  overlay.className = 'modal-overlay';

  const photoHtml = place.photo ? `<div class="modal-photo"><img src="${escapeAttr(place.photo)}" alt="${escapeAttr(place.name||'')}" /></div>` : '';

  const html = `
    <div class="modal-card" role="dialog" aria-modal="true" aria-label="Детали заведения">
      <button class="modal-close" aria-label="Закрыть">&times;</button>
      <div class="modal-body">
        ${photoHtml}
        <div class="modal-info">
          <h3 class="modal-name">${escapeHtml(place.name || '')}</h3>
          ${ place.category ? `<div class="modal-category small-muted">${escapeHtml(place.category)}</div>` : '' }
          <div class="modal-rating">${renderStarsInline(Number(place.rating || 0))}</div>
          <div class="modal-times small-muted">${escapeHtml(place.open_time || '')}${place.open_time && place.close_time ? ' - ' : ''}${escapeHtml(place.close_time || '')}</div>
          ${ place.address ? `<div class="modal-address"><strong>Адрес:</strong> ${escapeHtml(place.address)}</div>` : '' }
        </div>
      </div>
    </div>
  `;

  overlay.innerHTML = html;
  document.body.appendChild(overlay);

  // focus management
  const modalCard = overlay.querySelector('.modal-card');
  const closeBtn = overlay.querySelector('.modal-close');
  closeBtn.focus();

  function closeModal() {
    // cleanup listeners
    document.removeEventListener('keydown', onKeyDown);
    overlay.removeEventListener('click', onOverlayClick);
    if(overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  function onKeyDown(e){
    if(e.key === 'Escape') closeModal();
  }
  function onOverlayClick(e){
    if(e.target === overlay) closeModal();
  }

  closeBtn.addEventListener('click', closeModal);
  document.addEventListener('keydown', onKeyDown);
  overlay.addEventListener('click', onOverlayClick);
}


function renderStarsInline(r){
  const pct = Math.max(0, Math.min(5, r)) / 5 * 100;
  return `<div class="stars-outer"><div class="stars-inner" style="width:${pct}%">★★★★★</div><div class="stars-bg">★★★★★</div></div><span class="rating-num">${r}</span>`;
}

function escapeHtml(s){ return (s||'').toString().replace(/&/g,'&amp;').replace(/</g,'&lt;'); }
function escapeAttr(s){ return (s||'').toString().replace(/"/g,'&quot;'); }

export async function loadPlacesIntoHome() {
  const container = document.querySelector('.places-carousel');
  if(!container) return;
  container.innerHTML = '';
  const list = await fetchPlacesApi(12);
  if(!list.length){
    container.innerHTML = '<div class="muted">Пока нет заведений - добавьте на странице «Добавить заведение»</div>';
    return;
  }
  list.forEach(p => container.appendChild(renderPlaceCardForHome(p)));
}