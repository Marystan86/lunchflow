const DEV_USER_ID_KEY = "dev_user_id";

const devState = {
  checked: false,
  enabled: false,
  users: [],
};

function parsePositiveInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return Math.trunc(parsed);
}

function readStoredDevUserId() {
  try {
    return parsePositiveInt(localStorage.getItem(DEV_USER_ID_KEY));
  } catch (_) {
    return null;
  }
}

function writeStoredDevUserId(userId) {
  try {
    localStorage.setItem(DEV_USER_ID_KEY, String(userId));
  } catch (_) {
    // ignore storage write failures
  }
}

function pickDefaultUserId(users) {
  if (!Array.isArray(users) || users.length === 0) return null;
  const stored = readStoredDevUserId();
  if (stored && users.some((user) => Number(user?.id) === stored)) return stored;
  const firstId = parsePositiveInt(users[0]?.id);
  return firstId;
}

async function loadDevUsers(force = false) {
  if (devState.checked && !force) {
    return { enabled: devState.enabled, users: devState.users };
  }

  try {
    const response = await fetch("/api/dev/users", { cache: "no-store" });
    if (!response.ok) {
      devState.checked = true;
      devState.enabled = false;
      devState.users = [];
      return { enabled: false, users: [] };
    }

    const payload = await response.json().catch(() => []);
    const users = Array.isArray(payload)
      ? payload
          .map((item) => ({
            id: parsePositiveInt(item?.id),
            name: String(item?.name || "").trim(),
          }))
          .filter((item) => item.id && item.name)
      : [];

    devState.checked = true;
    devState.enabled = users.length > 0;
    devState.users = users;
    if (devState.enabled) {
      window.__DEV_MODE__ = true;
    }
    return { enabled: devState.enabled, users: devState.users };
  } catch (_) {
    devState.checked = true;
    devState.enabled = false;
    devState.users = [];
    return { enabled: false, users: [] };
  }
}

export async function isDevModeActive() {
  const state = await loadDevUsers();
  return Boolean(state.enabled);
}

export async function getDevUserHeader() {
  const { enabled, users } = await loadDevUsers();
  if (!enabled) return {};
  let selected = readStoredDevUserId();
  if (!selected) {
    selected = pickDefaultUserId(users);
    if (selected) writeStoredDevUserId(selected);
  }
  if (!selected) return {};
  return { "X-Dev-User-Id": String(selected) };
}

function ensureDevSwitcherRoot() {
  let root = document.getElementById("devUserSwitcher");
  if (root) return root;

  root = document.createElement("div");
  root.id = "devUserSwitcher";
  root.className = "dev-user-switcher hidden";
  root.innerHTML = `
    <label for="devUserSelect" class="dev-user-switcher-label">DEV USER</label>
    <select id="devUserSelect" class="dev-user-switcher-select"></select>
    <div id="devUserBadge" class="dev-user-switcher-badge"></div>
  `;
  document.body.appendChild(root);
  return root;
}

function renderDevSwitcher(users) {
  const root = ensureDevSwitcherRoot();
  const select = root.querySelector("#devUserSelect");
  const badge = root.querySelector("#devUserBadge");
  if (!(select instanceof HTMLSelectElement) || !(badge instanceof HTMLElement)) return;

  const selectedId = pickDefaultUserId(users);
  if (!selectedId) return;
  writeStoredDevUserId(selectedId);

  select.innerHTML = users
    .map((user) => `<option value="${user.id}">${user.name}</option>`)
    .join("");
  select.value = String(selectedId);

  const selectedUser = users.find((user) => Number(user.id) === Number(selectedId));
  badge.textContent = selectedUser ? `Testing as: ${selectedUser.name}` : "";

  if (!select.dataset.bound) {
    select.dataset.bound = "1";
    select.addEventListener("change", () => {
      const nextId = parsePositiveInt(select.value);
      if (!nextId) return;
      writeStoredDevUserId(nextId);
      window.location.reload();
    });
  }

  root.classList.remove("hidden");
}

export async function initDevUserSwitcher() {
  const { enabled, users } = await loadDevUsers();
  if (!enabled) return;
  renderDevSwitcher(users);
}

