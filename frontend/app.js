// Shared frontend helpers: API base, auth state, COLLECTED parser.

const API_BASE = "https://famli-backend.onrender.com";

const Auth = {
  save(token, userId, username) {
    localStorage.setItem("token", token);
    localStorage.setItem("user_id", String(userId));
    localStorage.setItem("username", username);
  },
  clear() {
    localStorage.removeItem("token");
    localStorage.removeItem("user_id");
    localStorage.removeItem("username");
  },
  token() {
    return localStorage.getItem("token");
  },
  userId() {
    const raw = localStorage.getItem("user_id");
    return raw ? parseInt(raw, 10) : null;
  },
  username() {
    return localStorage.getItem("username");
  },
  requireSession() {
    if (!this.userId() || !this.token()) {
      window.location.href = "index.html";
    }
  },
};

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(Auth.token() ? { Authorization: `Bearer ${Auth.token()}` } : {}),
    },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(Auth.token() ? { Authorization: `Bearer ${Auth.token()}` } : {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

// Bot replies end with a line like:
//   COLLECTED: {"goal_name": "...", "priority": null, ...}
// Returns { collected: object|null, displayText: string } where displayText
// has the COLLECTED line stripped for the chat bubble.
function parseCollected(botMessage) {
  if (!botMessage) return { collected: null, displayText: "" };
  const match = botMessage.match(/COLLECTED:\s*(\{.*\})\s*$/m);
  if (!match) return { collected: null, displayText: botMessage.trim() };
  let collected = null;
  try {
    collected = JSON.parse(match[1]);
  } catch (_) {
    collected = null;
  }
  const displayText = botMessage.replace(match[0], "").trim();
  return { collected, displayText };
}

// Escape HTML so user/bot content can't inject markup, then convert the
// limited markdown the LLM emits (currently just **bold**) into safe HTML.
function formatBotHtml(text) {
  if (!text) return "";
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  return escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

const FIELD_LABELS = [
  ["goal_name", "Goal Name"],
  ["priority", "Priority"],
  ["beneficiary", "Beneficiary"],
  ["current_age", "Current Age"],
  ["retirement_age", "Retirement Age"],
  ["life_expectancy", "Life Expectancy"],
  ["monthly_expense", "Monthly Expense (₹)"],
  ["inflation_rate", "Inflation Rate"],
  ["expected_return", "Expected Return"],
];

function renderCollectedPanel(panel, collected) {
  panel.innerHTML = "";
  for (const [key, label] of FIELD_LABELS) {
    const value = collected ? collected[key] : null;
    const li = document.createElement("li");
    li.className = value === null || value === undefined ? "pending" : "filled";
    const labelSpan = document.createElement("span");
    labelSpan.className = "field-label";
    labelSpan.textContent = label;
    const valueSpan = document.createElement("span");
    valueSpan.className = "field-value";
    valueSpan.textContent =
      value === null || value === undefined ? "—" : String(value);
    li.appendChild(labelSpan);
    li.appendChild(valueSpan);
    panel.appendChild(li);
  }
}
