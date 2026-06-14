async function loadUserData() {
  try {
    const res = await fetch("/api/users/me", { credentials: "include" });
    if (!res.ok) { window.location.href = "/login"; return null; }
    return await res.json();
  } catch {
    window.location.href = "/login";
    return null;
  }
}

async function loadPaidOrderCount() {
  try {
    const res = await fetch("/api/users/orders/paid-count", { credentials: "include" });
    if (!res.ok) return "—";
    const data = await res.json();
    return data.count ?? "—";
  } catch {
    return "—";
  }
}

function formatMemberSince(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
  } catch {
    return "—";
  }
}

const AVATAR_PALETTE = [
  "#e05c5c", "#e07c3a", "#c9973a", "#5aab6e", "#3a9fb5",
  "#5579c9", "#8b62c9", "#c95591", "#5aa5a5", "#7d8e3b",
];

function getAvatarColor(username) {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function renderInitialsAvatar(username) {
  const el = document.getElementById("profile-initials-avatar");
  if (!el || !username) return;
  el.textContent = username.charAt(0).toUpperCase();
  el.style.background = getAvatarColor(username);
}

function populatePage(user, paidCount) {
  renderInitialsAvatar(user.username);
  document.getElementById("profile-username").textContent = user.username;
  document.getElementById("profile-email").textContent = user.email;
  document.getElementById("stat-orders").textContent = paidCount;
  document.getElementById("stat-member").textContent = formatMemberSince(user.created_at);
  document.getElementById("new_username").value = user.username;
}

document.getElementById("usernameForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const btn = document.getElementById("saveUsernameBtn");
  const newUsername = document.getElementById("new_username").value.trim();
  const password = document.getElementById("confirm_password").value;

  if (!newUsername) {
    window.showToast?.("Please enter a new username.", 3500);
    return;
  }
  if (!password) {
    window.showToast?.("Please confirm your password.", 3500);
    return;
  }

  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    const res = await fetch("/api/users/me/username", {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_username: newUsername, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      const msg = data.detail || "Something went wrong. Please try again.";
      window.showModal?.({ type: "error", title: "Update Failed", message: msg });
      return;
    }

    renderInitialsAvatar(data.username);
    document.getElementById("profile-username").textContent = data.username;
    document.getElementById("new_username").value = data.username;
    document.getElementById("confirm_password").value = "";

    const navName = document.getElementById("nav-username");
    if (navName) navName.textContent = data.username;
    const mobileNavName = document.getElementById("mobile-nav-username");
    if (mobileNavName) mobileNavName.textContent = data.username;

    window.showToast?.("Username updated successfully! ✅", 3500);

  } catch {
    window.showModal?.({ type: "error", title: "Network Error", message: "Could not reach the server. Please check your connection." });
  } finally {
    btn.disabled = false;
    btn.textContent = "Save Username";
  }
});

let _currentUserId = null;

document.getElementById("deleteAccountForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("delete_password").value;
  if (!password) {
    window.showToast?.("Please enter your password to confirm deletion.", 3500);
    return;
  }

  window.showModal?.({
    type: "error",
    title: "Delete Account Forever?",
    message: "This will permanently erase your account, all orders, and payment records. There is NO way to recover this data. Are you absolutely sure?",
    primary: { label: "Yes, Delete My Account", action: () => performDelete(password) },
    secondary: { label: "Cancel", action: () => {} },
  });
});

async function performDelete(password) {
  if (!_currentUserId) return;
  const btn = document.getElementById("deleteAccountBtn");
  btn.disabled = true;
  btn.textContent = "Deleting…";

  try {
    const res = await fetch(`/api/users/delete/${_currentUserId}`, {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });

    if (res.status === 204) {
      sessionStorage.removeItem("pe_user");
      window.showToast?.("Account deleted. Goodbye! 👋", 3000);
      setTimeout(() => { window.location.href = "/"; }, 1500);
      return;
    }

    const data = await res.json();
    window.showModal?.({ type: "error", title: "Deletion Failed", message: data.detail || "Failed to delete account." });

  } catch {
    window.showModal?.({ type: "error", title: "Network Error", message: "Could not reach the server." });
  } finally {
    btn.disabled = false;
    btn.textContent = "🗑️ Permanently Delete My Account";
  }
}

(async () => {
  const [user, paidCount] = await Promise.all([loadUserData(), loadPaidOrderCount()]);
  if (user) {
    _currentUserId = user.id;
    populatePage(user, paidCount);
  }
})();
