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
// The label may be wrapped in markdown bold (**COLLECTED:**), and the JSON
// may contain embedded newlines if the LLM split a long value across lines.
// Returns { collected: object|null, displayText: string } where displayText
// has the COLLECTED line stripped for the chat bubble.
function parseCollected(botMessage) {
  if (!botMessage) return { collected: null, displayText: "" };
  // [\s\S] matches any character including newlines (since /s flag is not
  // universally supported across older browsers, this is the portable trick).
  const match = botMessage.match(
    /\**\s*COLLECTED:\s*\**\s*(\{[\s\S]*\})\s*$/,
  );
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

// Format a bare number string with Indian-style digit grouping
// (e.g. "1437934.92" -> "14,37,934.92"). The LLM is instructed to emit
// rupee numbers without commas; we add them here for display.
function formatIndianNumber(rawDigits) {
  if (rawDigits == null) return "";
  const num = Number(rawDigits);
  if (!Number.isFinite(num)) return String(rawDigits);
  return num.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// Find bare "₹<digits>[.decimals]" sequences in the bot's text and replace
// each with the Indian-comma-formatted version. Runs after HTML-escape so
// no markup injection risk.
function formatRupeesInText(text) {
  // Match ₹ followed by digits (no commas), optional decimal part.
  // Lookbehind avoids partial matches inside already-grouped strings.
  return text.replace(/₹\s*(\d+(?:\.\d+)?)/g, (_, digits) => {
    return `₹${formatIndianNumber(digits)}`;
  });
}

// Escape HTML so user/bot content can't inject markup, then format any
// rupee numbers with Indian-style commas, then convert the limited
// markdown the LLM emits (currently just **bold**) into safe HTML.
function formatBotHtml(text) {
  if (!text) return "";
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const withRupees = formatRupeesInText(escaped);
  return withRupees.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
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

function formatRateValue(key, value) {
  if (key !== "inflation_rate" && key !== "expected_return") return String(value);
  const num = Number(value);
  if (Number.isFinite(num) && num > 0 && num <= 1) {
    return `${(num * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
  }
  return String(value);
}

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
      value === null || value === undefined ? "—" : formatRateValue(key, value);
    li.appendChild(labelSpan);
    li.appendChild(valueSpan);
    panel.appendChild(li);
  }
}
