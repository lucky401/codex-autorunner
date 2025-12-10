import { api, flash, statusPill } from "./utils.js";
import { loadState } from "./state.js";
import { publish } from "./bus.js";

// ─────────────────────────────────────────────────────────────────────────────
// Constants & State
// ─────────────────────────────────────────────────────────────────────────────

const DOC_TYPES = ["todo", "progress", "opinions", "spec"];
const CHAT_HISTORY_LIMIT = 8;

const docButtons = document.querySelectorAll(".chip[data-doc]");
let docsCache = { todo: "", progress: "", opinions: "", spec: "" };
let activeDoc = "todo";

const chatDecoder = new TextDecoder();
const chatState = Object.fromEntries(
  DOC_TYPES.map((k) => [k, createChatState()])
);

// ─────────────────────────────────────────────────────────────────────────────
// UI Element References
// ─────────────────────────────────────────────────────────────────────────────

const chatUI = {
  status: document.getElementById("doc-chat-status"),
  response: document.getElementById("doc-chat-response"),
  responseWrapper: document.getElementById("doc-chat-response-wrapper"),
  history: document.getElementById("doc-chat-history"),
  historyDetails: document.getElementById("doc-chat-history-details"),
  historyCount: document.getElementById("doc-chat-history-count"),
  error: document.getElementById("doc-chat-error"),
  input: document.getElementById("doc-chat-input"),
  send: document.getElementById("doc-chat-send"),
  cancel: document.getElementById("doc-chat-cancel"),
  hint: document.getElementById("doc-chat-hint"),
};

// ─────────────────────────────────────────────────────────────────────────────
// Chat State Management
// ─────────────────────────────────────────────────────────────────────────────

function createChatState() {
  return {
    history: [],
    status: "idle",
    statusText: "",
    error: "",
    streamText: "",
    controller: null,
  };
}

function getChatState(kind = activeDoc) {
  if (!chatState[kind]) {
    chatState[kind] = createChatState();
  }
  return chatState[kind];
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

function parseChatPayload(payload) {
  if (!payload) return { response: "" };
  if (typeof payload === "string") return { response: payload };
  if (payload.status && payload.status !== "ok") {
    return { error: payload.detail || "Doc chat failed" };
  }
  return {
    response: payload.agent_message || payload.message || payload.content || "",
    content: payload.content || "",
  };
}

function parseMaybeJson(raw) {
  try {
    return JSON.parse(raw);
  } catch (err) {
    return raw;
  }
}

function truncateText(text, maxLen) {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, " ").trim();
  return normalized.length > maxLen
    ? normalized.slice(0, maxLen) + "…"
    : normalized;
}

function autoResizeTextarea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = textarea.scrollHeight + "px";
}

function getDocTextarea() {
  return document.getElementById("doc-content");
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat UI Rendering
// ─────────────────────────────────────────────────────────────────────────────

function applyDocUpdateFromChat(kind, content) {
  if (!content) return false;
  const textarea = getDocTextarea();
  const viewingSameDoc = activeDoc === kind;
  if (viewingSameDoc && textarea) {
    const cached = docsCache[kind] || "";
    if (textarea.value !== cached) {
      const ok = window.confirm(
        `You have unsaved ${kind.toUpperCase()} edits. Overwrite with chat result?`
      );
      if (!ok) {
        flash(
          `Kept your unsaved ${kind.toUpperCase()} edits; chat result not applied.`
        );
        return false;
      }
    }
  }

  docsCache[kind] = content;
  if (viewingSameDoc && textarea) {
    textarea.value = content;
    document.getElementById(
      "doc-status"
    ).textContent = `Editing ${kind.toUpperCase()}`;
  }
  publish("docs:updated", { kind, content });
  if (kind === "todo") {
    renderTodoPreview(content);
    loadState({ notify: false }).catch(() => {});
  }
  return true;
}

function renderChat(kind = activeDoc) {
  if (kind !== activeDoc) return;
  const state = getChatState(kind);
  const latest = state.history[0];
  const isRunning = state.status === "running";
  const hasError = !!state.error;

  // Update status pill
  const pillState = isRunning
    ? "running"
    : state.status === "error"
    ? "error"
    : "idle";
  statusPill(chatUI.status, pillState);

  // Update input state
  chatUI.send.disabled = isRunning;
  chatUI.input.disabled = isRunning;
  chatUI.cancel.classList.toggle("hidden", !isRunning);

  // Update hint text
  chatUI.hint.textContent = isRunning
    ? state.statusText || "Processing..."
    : "Shift+Enter to send";

  // Handle error display
  if (hasError) {
    chatUI.error.textContent = state.error;
    chatUI.error.classList.remove("hidden");
  } else {
    chatUI.error.textContent = "";
    chatUI.error.classList.add("hidden");
  }

  // Compute response text
  let responseText = "";
  if (isRunning) {
    responseText = state.streamText || "Waiting for response...";
  } else if (latest && (latest.response || latest.error)) {
    responseText = latest.response || latest.error;
  }

  // Show/hide response wrapper based on content
  const hasResponse = !!responseText || hasError;
  chatUI.responseWrapper.classList.toggle("hidden", !hasResponse);
  chatUI.response.textContent = responseText;
  chatUI.response.classList.toggle("muted", isRunning && !state.streamText);

  renderChatHistory(state);
}

function renderChatHistory(state) {
  if (!chatUI.history) return;

  const count = state.history.length;
  chatUI.historyCount.textContent = count;

  // Hide history details if empty
  if (chatUI.historyDetails) {
    chatUI.historyDetails.style.display = count === 0 ? "none" : "";
  }

  chatUI.history.innerHTML = "";
  if (count === 0) return;

  state.history.slice(0, CHAT_HISTORY_LIMIT).forEach((entry) => {
    const wrapper = document.createElement("div");
    wrapper.className = `doc-chat-entry ${entry.status}`;

    const prompt = document.createElement("div");
    prompt.className = "prompt";
    prompt.textContent = truncateText(entry.prompt, 60);
    prompt.title = entry.prompt;

    const response = document.createElement("div");
    response.className = "response";
    const preview = entry.error || entry.response || "(pending...)";
    response.textContent = truncateText(preview, 80);
    response.title = preview;

    const meta = document.createElement("div");
    meta.className = "meta";

    const dot = document.createElement("span");
    dot.className = "status-dot";

    const stamp = document.createElement("span");
    stamp.textContent = entry.time
      ? new Date(entry.time).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : entry.status;

    meta.appendChild(dot);
    meta.appendChild(stamp);

    wrapper.appendChild(prompt);
    wrapper.appendChild(response);
    wrapper.appendChild(meta);
    chatUI.history.appendChild(wrapper);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Actions & Error Handling
// ─────────────────────────────────────────────────────────────────────────────

function markChatError(state, entry, message) {
  entry.status = "error";
  entry.error = message;
  state.error = message;
  state.status = "error";
  renderChat();
}

function cancelDocChat() {
  const state = getChatState(activeDoc);
  if (state.status !== "running") return;
  if (state.controller) state.controller.abort();
  const entry = state.history[0];
  if (entry && entry.status === "running") {
    entry.status = "error";
    entry.error = "Cancelled";
  }
  state.status = "idle";
  state.controller = null;
  renderChat();
}

async function sendDocChat() {
  const message = (chatUI.input.value || "").trim();
  const state = getChatState(activeDoc);
  if (!message) {
    state.error = "Enter a message to send.";
    renderChat();
    return;
  }
  if (state.status === "running") return;

  const entry = {
    id: `${Date.now()}`,
    prompt: message,
    response: "",
    status: "running",
    time: Date.now(),
    lastAppliedContent: null,
  };
  state.history.unshift(entry);
  if (state.history.length > CHAT_HISTORY_LIMIT * 2) {
    state.history.length = CHAT_HISTORY_LIMIT * 2;
  }
  state.status = "running";
  state.error = "";
  state.streamText = "";
  state.statusText = "queued";
  state.controller = new AbortController();

  renderChat();
  chatUI.input.value = "";
  chatUI.input.style.height = "auto"; // Reset textarea height
  chatUI.input.focus();

  try {
    await performDocChatRequest(activeDoc, entry, state);
    if (entry.status !== "error") {
      state.status = "idle";
      state.error = "";
    }
  } catch (err) {
    if (err.name === "AbortError") {
      entry.status = "error";
      entry.error = "Cancelled";
      state.error = "";
      state.status = "idle";
    } else {
      markChatError(state, entry, err.message || "Doc chat failed");
    }
  } finally {
    state.controller = null;
    if (state.status !== "running") {
      renderChat();
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Networking & Streaming
// ─────────────────────────────────────────────────────────────────────────────

async function performDocChatRequest(kind, entry, state) {
  const endpoint = `/api/docs/${kind}/chat`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: entry.prompt, stream: true }),
    signal: state.controller.signal,
  });

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      detail = parsed.detail || parsed.error || text;
    } catch (err) {
      // ignore parse errors
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream")) {
    await readChatStream(res, state, entry, kind);
    if (entry.status !== "error" && entry.status !== "done") {
      entry.status = "done";
    }
  } else {
    const payload = contentType.includes("application/json")
      ? await res.json()
      : await res.text();
    applyChatResult(payload, state, entry, kind);
  }
}

async function readChatStream(res, state, entry, kind) {
  if (!res.body) throw new Error("Streaming not supported in this browser");
  const reader = res.body.getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += chatDecoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop();
    for (const chunk of chunks) {
      if (!chunk.trim()) continue;
      let event = "message";
      const dataLines = [];
      chunk.split("\n").forEach((line) => {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart());
        }
      });
      const data = dataLines.join("\n");
      await handleStreamEvent(event || "message", data, state, entry, kind);
    }
  }
}

async function handleStreamEvent(event, rawData, state, entry, kind) {
  const parsed = parseMaybeJson(rawData);
  if (event === "status") {
    state.statusText =
      typeof parsed === "string" ? parsed : parsed.status || "";
    renderChat(kind);
    return;
  }
  if (event === "token") {
    const token =
      typeof parsed === "string"
        ? parsed
        : parsed.token || parsed.text || rawData || "";
    entry.response = (entry.response || "") + token;
    state.streamText = entry.response;
    renderChat(kind);
    return;
  }
  if (event === "update") {
    const payload = parseChatPayload(parsed);
    entry.response = payload.response || entry.response;
    state.streamText = entry.response;
    if (payload.content && payload.content !== entry.lastAppliedContent) {
      const applied = applyDocUpdateFromChat(kind, payload.content);
      if (applied) {
        entry.lastAppliedContent = payload.content;
      }
    }
    renderChat(kind);
    return;
  }
  if (event === "error") {
    const message =
      (parsed && parsed.detail) ||
      (parsed && parsed.error) ||
      rawData ||
      "Doc chat failed";
    markChatError(state, entry, message);
    throw new Error(message);
  }
  if (event === "done" || event === "finish") {
    entry.status = "done";
    return;
  }
}

function applyChatResult(payload, state, entry, kind = activeDoc) {
  const parsed = parseChatPayload(payload);
  if (parsed.error) {
    markChatError(state, entry, parsed.error);
    return;
  }
  entry.status = "done";
  entry.response = parsed.response || "(no response)";
  state.streamText = entry.response;
  if (parsed.content) {
    const applied = applyDocUpdateFromChat(kind, parsed.content);
    if (applied) {
      entry.lastAppliedContent = parsed.content;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// TODO Preview
// ─────────────────────────────────────────────────────────────────────────────

function renderTodoPreview(text) {
  const list = document.getElementById("todo-preview-list");
  list.innerHTML = "";
  const lines = text.split("\n").map((l) => l.trim());
  const todos = lines.filter((l) => l.startsWith("- [")).slice(0, 8);
  if (todos.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No TODO items found.";
    list.appendChild(li);
    return;
  }
  todos.forEach((line) => {
    const li = document.createElement("li");
    const box = document.createElement("div");
    box.className = "box";
    const done = line.toLowerCase().startsWith("- [x]");
    if (done) box.classList.add("done");
    const textSpan = document.createElement("span");
    textSpan.textContent = line.substring(5).trim();
    li.appendChild(box);
    li.appendChild(textSpan);
    list.appendChild(li);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Doc CRUD Operations
// ─────────────────────────────────────────────────────────────────────────────

async function loadDocs() {
  try {
    const data = await api("/api/docs");
    docsCache = { ...docsCache, ...data };
    setDoc(activeDoc);
    renderTodoPreview(docsCache.todo);
    document.getElementById("doc-status").textContent = "Loaded";
    publish("docs:loaded", docsCache);
  } catch (err) {
    flash(err.message);
  }
}

function setDoc(kind) {
  activeDoc = kind;
  docButtons.forEach((btn) =>
    btn.classList.toggle("active", btn.dataset.doc === kind)
  );
  const textarea = document.getElementById("doc-content");
  textarea.value = docsCache[kind] || "";
  document.getElementById(
    "doc-status"
  ).textContent = `Editing ${kind.toUpperCase()}`;
  renderChat(kind);
}

async function saveDoc() {
  const content = document.getElementById("doc-content").value;
  const saveBtn = document.getElementById("save-doc");
  saveBtn.disabled = true;
  try {
    await api(`/api/docs/${activeDoc}`, { method: "PUT", body: { content } });
    docsCache[activeDoc] = content;
    flash(`${activeDoc.toUpperCase()} saved`);
    publish("docs:updated", { kind: activeDoc, content });
    if (activeDoc === "todo") {
      renderTodoPreview(content);
      await loadState({ notify: false });
    }
  } catch (err) {
    flash(err.message);
  } finally {
    saveBtn.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────────────────────────────────

export function initDocs() {
  docButtons.forEach((btn) =>
    btn.addEventListener("click", () => {
      setDoc(btn.dataset.doc);
    })
  );
  document.getElementById("save-doc").addEventListener("click", saveDoc);
  document.getElementById("reload-doc").addEventListener("click", loadDocs);
  document
    .getElementById("refresh-preview")
    .addEventListener("click", loadDocs);
  document.getElementById("ingest-spec").addEventListener("click", ingestSpec);
  document.getElementById("clear-docs").addEventListener("click", clearDocs);
  chatUI.send.addEventListener("click", sendDocChat);
  chatUI.cancel.addEventListener("click", cancelDocChat);

  // Shift+Enter sends, Enter adds newline (default textarea behavior)
  chatUI.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.shiftKey) {
      e.preventDefault();
      sendDocChat();
    }
  });

  // Clear errors on input and auto-resize textarea
  chatUI.input.addEventListener("input", () => {
    const state = getChatState(activeDoc);
    if (state.error) {
      state.error = "";
      renderChat();
    }
    autoResizeTextarea(chatUI.input);
  });

  loadDocs();
  renderChat(activeDoc);
}

async function ingestSpec() {
  const needsForce = ["todo", "progress", "opinions"].some(
    (k) => (docsCache[k] || "").trim().length > 0
  );
  if (needsForce) {
    const ok = window.confirm(
      "Overwrite TODO/PROGRESS/OPINIONS from SPEC? Existing content will be replaced."
    );
    if (!ok) return;
  }
  const button = document.getElementById("ingest-spec");
  button.disabled = true;
  try {
    const data = await api("/api/ingest-spec", {
      method: "POST",
      body: { force: needsForce },
    });
    docsCache = { ...docsCache, ...data };
    setDoc(activeDoc);
    renderTodoPreview(docsCache.todo);
    publish("docs:updated", { kind: "todo", content: docsCache.todo });
    publish("docs:updated", { kind: "progress", content: docsCache.progress });
    publish("docs:updated", { kind: "opinions", content: docsCache.opinions });
    await loadState({ notify: false });
    flash("Ingested SPEC into docs");
  } catch (err) {
    flash(err.message, "error");
  } finally {
    button.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Spec Ingestion & Doc Clearing
// ─────────────────────────────────────────────────────────────────────────────

async function clearDocs() {
  const confirmFirst = window.confirm(
    "Clear TODO/PROGRESS/OPINIONS? This cannot be undone."
  );
  if (!confirmFirst) return;
  const confirmSecond = window.prompt('Type "CLEAR" to confirm reset');
  if (!confirmSecond || confirmSecond.trim().toUpperCase() !== "CLEAR") {
    flash("Clear cancelled");
    return;
  }
  const button = document.getElementById("clear-docs");
  button.disabled = true;
  try {
    const data = await api("/api/docs/clear", { method: "POST" });
    docsCache = { ...docsCache, ...data };
    await loadDocs();
    flash("Cleared TODO/PROGRESS/OPINIONS");
  } catch (err) {
    flash(err.message, "error");
  } finally {
    button.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Test Exports
// ─────────────────────────────────────────────────────────────────────────────

export const __docChatTest = {
  applyChatResult,
  applyDocUpdateFromChat,
  getChatState,
  handleStreamEvent,
  performDocChatRequest,
  renderChat,
  setDoc,
};
