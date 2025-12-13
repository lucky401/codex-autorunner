import { flash, buildWsUrl } from "./utils.js";
import { CONSTANTS } from "./constants.js";
import { initVoiceInput } from "./voice.js";

let term = null;
let fitAddon = null;
let socket = null;
let statusEl = null;
let overlayEl = null;
let connectBtn = null;
let disconnectBtn = null;
let resumeBtn = null;
let inputDisposable = null;
let intentionalDisconnect = false;
let reconnectTimer = null;
let reconnectAttempts = 0;
let voiceBtn = null;
let voiceStatus = null;
let voiceController = null;
let voiceKeyActive = false;
let mobileVoiceBtn = null;
let mobileVoiceController = null;
let resizeRaf = null;

// Text input panel state
let terminalSectionEl = null;
let textInputToggleBtn = null;
let textInputPanelEl = null;
let textInputTextareaEl = null;
let textInputSendBtn = null;
let textInputClearBtn = null;
let textInputAppendEnterEl = null;
let textInputEnabled = false;
let textInputAppendEnter = true;

// Mobile controls state
let mobileControlsEl = null;
let ctrlActive = false;
let altActive = false;

const textEncoder = new TextEncoder();

const TEXT_INPUT_STORAGE_KEYS = Object.freeze({
  enabled: "codex_terminal_text_input_enabled",
  appendEnter: "codex_terminal_text_input_append_enter",
});

const TEXT_INPUT_SIZE_LIMITS = Object.freeze({
  warnBytes: 100 * 1024,
  maxBytes: 500 * 1024,
});

const TOUCH_OVERRIDE = (() => {
  try {
    const params = new URLSearchParams(window.location.search);
    const truthy = new Set(["1", "true", "yes", "on"]);
    const falsy = new Set(["0", "false", "no", "off"]);

    const touchParam = params.get("force_touch") ?? params.get("touch");
    if (touchParam !== null) {
      const value = String(touchParam).toLowerCase();
      if (truthy.has(value)) return true;
      if (falsy.has(value)) return false;
    }

    const desktopParam = params.get("force_desktop") ?? params.get("desktop");
    if (desktopParam !== null) {
      const value = String(desktopParam).toLowerCase();
      if (truthy.has(value)) return false;
      if (falsy.has(value)) return true;
    }

    return null;
  } catch (_err) {
    return null;
  }
})();

// Check if device has touch capability
function isTouchDevice() {
  if (TOUCH_OVERRIDE !== null) return TOUCH_OVERRIDE;
  return "ontouchstart" in window || navigator.maxTouchPoints > 0;
}

// Send a key sequence to the terminal
function sendKey(seq) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;

  // If ctrl modifier is active, convert to ctrl code
  if (ctrlActive && seq.length === 1) {
    const char = seq.toUpperCase();
    const code = char.charCodeAt(0) - 64;
    if (code >= 1 && code <= 26) {
      seq = String.fromCharCode(code);
    }
  }

  socket.send(textEncoder.encode(seq));

  // Reset modifiers after sending (unless it was just a modifier toggle)
  ctrlActive = false;
  altActive = false;
  updateModifierButtons();
}

function normalizeNewlines(text) {
  return (text || "").replace(/\r\n?/g, "\n");
}

function sendText(text, options = {}) {
  const appendNewline = Boolean(options.appendNewline);
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    flash("Connect the terminal first", "error");
    return false;
  }

  let payload = normalizeNewlines(text);
  if (!payload) return false;

  if (appendNewline && !payload.endsWith("\n")) {
    payload = `${payload}\n`;
  }

  const encoded = textEncoder.encode(payload);
  if (encoded.byteLength > TEXT_INPUT_SIZE_LIMITS.maxBytes) {
    flash(
      `Text is too large to send (${Math.round(encoded.byteLength / 1024)}KB).`,
      "error"
    );
    return false;
  }
  if (encoded.byteLength > TEXT_INPUT_SIZE_LIMITS.warnBytes) {
    flash(
      `Large paste (${Math.round(encoded.byteLength / 1024)}KB); sending may be slow.`,
      "info"
    );
  }

  socket.send(encoded);
  return true;
}

// Send Ctrl+key combo
function sendCtrl(char) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  const code = char.toUpperCase().charCodeAt(0) - 64;
  socket.send(textEncoder.encode(String.fromCharCode(code)));
}

// Update modifier button visual states
function updateModifierButtons() {
  const ctrlBtn = document.getElementById("tmb-ctrl");
  const altBtn = document.getElementById("tmb-alt");
  if (ctrlBtn) ctrlBtn.classList.toggle("active", ctrlActive);
  if (altBtn) altBtn.classList.toggle("active", altActive);
}

// Initialize mobile controls
function initMobileControls() {
  mobileControlsEl = document.getElementById("terminal-mobile-controls");
  if (!mobileControlsEl) return;

  // Only show on touch devices
  if (!isTouchDevice()) {
    mobileControlsEl.style.display = "none";
    return;
  }

  // Handle all key buttons
  mobileControlsEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".tmb-key");
    if (!btn) return;

    e.preventDefault();

    // Handle modifier toggles
    const modKey = btn.dataset.key;
    if (modKey === "ctrl") {
      ctrlActive = !ctrlActive;
      updateModifierButtons();
      return;
    }
    if (modKey === "alt") {
      altActive = !altActive;
      updateModifierButtons();
      return;
    }

    // Handle Ctrl+X combos
    const ctrlChar = btn.dataset.ctrl;
    if (ctrlChar) {
      sendCtrl(ctrlChar);
      if (isTouchDevice() && textInputEnabled) {
        setTimeout(() => safeFocus(textInputTextareaEl), 0);
      }
      return;
    }

    // Handle direct sequences (arrows, esc, tab)
    const seq = btn.dataset.seq;
    if (seq) {
      sendKey(seq);
      if (isTouchDevice() && textInputEnabled) {
        setTimeout(() => safeFocus(textInputTextareaEl), 0);
      }
      return;
    }
  });

  // Add haptic feedback on touch if available
  mobileControlsEl.addEventListener(
    "touchstart",
    (e) => {
      if (e.target.closest(".tmb-key") && navigator.vibrate) {
        navigator.vibrate(10);
      }
    },
    { passive: true }
  );
}

function readBoolFromStorage(key, fallback) {
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  return fallback;
}

function writeBoolToStorage(key, value) {
  localStorage.setItem(key, value ? "1" : "0");
}

function safeFocus(el) {
  if (!el) return;
  try {
    el.focus({ preventScroll: true });
  } catch (err) {
    try {
      el.focus();
    } catch (_err) {
      // ignore
    }
  }
}

function scheduleResizeAfterLayout() {
  if (resizeRaf) {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = null;
  }

  // Double-rAF helps ensure layout changes (e.g. toggled classes) have applied.
  resizeRaf = requestAnimationFrame(() => {
    resizeRaf = requestAnimationFrame(() => {
      resizeRaf = null;
      handleResize();
    });
  });
}

function setTextInputEnabled(enabled, options = {}) {
  textInputEnabled = Boolean(enabled);
  writeBoolToStorage(TEXT_INPUT_STORAGE_KEYS.enabled, textInputEnabled);

  const focus = options.focus !== false;
  const shouldFocusTextarea = focus && (isTouchDevice() || options.focusTextarea);

  textInputToggleBtn?.setAttribute(
    "aria-expanded",
    textInputEnabled ? "true" : "false"
  );
  textInputPanelEl?.classList.toggle("hidden", !textInputEnabled);
  textInputPanelEl?.setAttribute(
    "aria-hidden",
    textInputEnabled ? "false" : "true"
  );
  terminalSectionEl?.classList.toggle("text-input-open", textInputEnabled);

  // The panel changes the terminal container height via CSS; refit xterm and
  // (if connected) notify the backend so rows/cols stay in sync.
  scheduleResizeAfterLayout();

  if (textInputEnabled && shouldFocusTextarea) {
    requestAnimationFrame(() => {
      safeFocus(textInputTextareaEl);
    });
  } else if (!isTouchDevice()) {
    term?.focus();
  }
}

function updateTextInputConnected(connected) {
  if (textInputSendBtn) textInputSendBtn.disabled = !connected;
  if (textInputTextareaEl) textInputTextareaEl.disabled = false;
  if (textInputClearBtn) textInputClearBtn.disabled = false;
  if (textInputAppendEnterEl) textInputAppendEnterEl.disabled = false;
}

function sendFromTextarea() {
  const text = textInputTextareaEl?.value || "";
  const ok = sendText(text, { appendNewline: textInputAppendEnter });
  if (!ok) return;

  if (textInputTextareaEl) {
    textInputTextareaEl.value = "";
  }

  if (isTouchDevice()) {
    requestAnimationFrame(() => {
      safeFocus(textInputTextareaEl);
    });
  } else {
    term?.focus();
  }
}

function initTextInputPanel() {
  terminalSectionEl = document.getElementById("terminal");
  textInputToggleBtn = document.getElementById("terminal-text-input-toggle");
  textInputPanelEl = document.getElementById("terminal-text-input");
  textInputTextareaEl = document.getElementById("terminal-textarea");
  textInputSendBtn = document.getElementById("terminal-text-send");
  textInputClearBtn = document.getElementById("terminal-text-clear");
  textInputAppendEnterEl = document.getElementById(
    "terminal-text-append-enter"
  );

  if (
    !terminalSectionEl ||
    !textInputToggleBtn ||
    !textInputPanelEl ||
    !textInputTextareaEl ||
    !textInputSendBtn ||
    !textInputClearBtn ||
    !textInputAppendEnterEl
  ) {
    return;
  }

  textInputEnabled = readBoolFromStorage(
    TEXT_INPUT_STORAGE_KEYS.enabled,
    isTouchDevice()
  );
  textInputAppendEnter = readBoolFromStorage(
    TEXT_INPUT_STORAGE_KEYS.appendEnter,
    true
  );

  textInputAppendEnterEl.checked = textInputAppendEnter;

  textInputToggleBtn.addEventListener("click", () => {
    setTextInputEnabled(!textInputEnabled, { focus: true, focusTextarea: true });
  });

  textInputAppendEnterEl.addEventListener("change", () => {
    textInputAppendEnter = Boolean(textInputAppendEnterEl.checked);
    writeBoolToStorage(TEXT_INPUT_STORAGE_KEYS.appendEnter, textInputAppendEnter);
  });

  textInputSendBtn.addEventListener("click", () => {
    if (textInputSendBtn?.disabled) {
      flash("Connect the terminal first", "error");
      return;
    }
    sendFromTextarea();
  });

  textInputClearBtn.addEventListener("click", () => {
    if (textInputTextareaEl) textInputTextareaEl.value = "";
    if (isTouchDevice()) {
      requestAnimationFrame(() => {
        safeFocus(textInputTextareaEl);
      });
    }
  });

  textInputTextareaEl.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    if (e.isComposing) return;
    const value = textInputTextareaEl?.value || "";
    if (normalizeNewlines(value).includes("\n")) {
      return;
    }
    e.preventDefault();
    sendFromTextarea();
  });

  setTextInputEnabled(textInputEnabled, { focus: false });
  updateTextInputConnected(Boolean(socket && socket.readyState === WebSocket.OPEN));
}

function setStatus(message) {
  if (statusEl) {
    statusEl.textContent = message;
  }
}

function getFontSize() {
  return window.innerWidth < 640 ? 10 : 13;
}

function ensureTerminal() {
  if (!window.Terminal || !window.FitAddon) {
    setStatus("xterm assets missing; reload or check /static/vendor");
    flash("xterm assets missing; reload the page", "error");
    return false;
  }
  if (term) {
    return true;
  }
  const container = document.getElementById("terminal-container");
  if (!container) return false;
  term = new window.Terminal({
    convertEol: true,
    fontFamily:
      '"JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
    fontSize: getFontSize(),
    cursorBlink: true,
    rows: 24,
    cols: 100,
    theme: CONSTANTS.THEME.XTERM,
  });
  fitAddon = new window.FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(container);
  term.write('Press "Start session" to launch Codex TUI...\r\n');
  if (!inputDisposable) {
    inputDisposable = term.onData((data) => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(textEncoder.encode(data));
    });
  }
  return true;
}

function teardownSocket() {
  if (socket) {
    socket.onclose = null;
    socket.onerror = null;
    socket.onmessage = null;
    socket.onopen = null;
    try {
      socket.close();
    } catch (err) {
      // ignore
    }
  }
  socket = null;
}

function updateButtons(connected) {
  if (connectBtn) connectBtn.disabled = connected;
  if (disconnectBtn) disconnectBtn.disabled = !connected;
  if (resumeBtn) resumeBtn.disabled = connected;
  updateTextInputConnected(connected);
  const voiceUnavailable = voiceBtn?.classList.contains("disabled");
  if (voiceBtn && !voiceUnavailable) {
    voiceBtn.disabled = !connected;
    voiceBtn.classList.toggle("voice-disconnected", !connected);
  }
  // Also update mobile voice button state
  const mobileVoiceUnavailable = mobileVoiceBtn?.classList.contains("disabled");
  if (mobileVoiceBtn && !mobileVoiceUnavailable) {
    mobileVoiceBtn.disabled = !connected;
    mobileVoiceBtn.classList.toggle("voice-disconnected", !connected);
  }
  if (voiceStatus && !voiceUnavailable && !connected) {
    voiceStatus.textContent = "Connect to use voice";
    voiceStatus.classList.remove("hidden");
  } else if (
    voiceStatus &&
    !voiceUnavailable &&
    connected &&
    voiceController &&
    voiceStatus.textContent === "Connect to use voice"
  ) {
    voiceStatus.textContent = "Hold to talk (Alt+V)";
    voiceStatus.classList.remove("hidden");
  }
}

function handleResize() {
  if (!fitAddon || !term) return;

  // Update font size based on current window width
  const newFontSize = getFontSize();
  if (term.options.fontSize !== newFontSize) {
    term.options.fontSize = newFontSize;
  }

  // Only send resize if connected
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    try {
      fitAddon.fit();
    } catch (e) {
      // ignore fit errors when not visible
    }
    return;
  }

  fitAddon.fit();
  socket.send(
    JSON.stringify({
      type: "resize",
      cols: term.cols,
      rows: term.rows,
    })
  );
}

function connect(options = {}) {
  const resume = Boolean(options.resume);
  if (!ensureTerminal()) return;
  if (socket && socket.readyState === WebSocket.OPEN) return;

  // cancel any pending reconnect
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  teardownSocket();
  intentionalDisconnect = false;

  const queryParams = new URLSearchParams();
  if (resume) queryParams.append("mode", "resume");

  const savedSessionId = localStorage.getItem("codex_terminal_session_id");
  if (savedSessionId) {
    queryParams.append("session_id", savedSessionId);
  }

  const queryString = queryParams.toString();
  const wsUrl = buildWsUrl(
    CONSTANTS.API.TERMINAL_ENDPOINT,
    queryString ? `?${queryString}` : ""
  );
  socket = new WebSocket(wsUrl);
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    reconnectAttempts = 0;
    overlayEl?.classList.add("hidden");
    setStatus(resume ? "Connected (resume)" : "Connected");
    updateButtons(true);
    fitAddon.fit();
    handleResize();
    if (resume) {
      term?.write("\r\nLaunching resume flow...\r\n");
    }
  };

  socket.onmessage = (event) => {
    if (typeof event.data === "string") {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "hello") {
          if (payload.session_id) {
            localStorage.setItem(
              "codex_terminal_session_id",
              payload.session_id
            );
          }
          if (payload.history) {
            // Replay history if provided (though server might send it as binary chunks)
            // If history is sent as base64 or something in this payload
          }
        } else if (payload.type === "exit") {
          term?.write(
            `\r\n[session ended${
              payload.code !== null ? ` (code ${payload.code})` : ""
            }] \r\n`
          );
          // Clear saved session on explicit exit
          localStorage.removeItem("codex_terminal_session_id");
          // Treat exit as an intentional disconnect or at least not something to auto-reconnect to immediately
          intentionalDisconnect = true;
          disconnect();
        } else if (payload.type === "error") {
          if (
            payload.message &&
            payload.message.includes("Session not found")
          ) {
            localStorage.removeItem("codex_terminal_session_id");
          }
          flash(payload.message || "Terminal error", "error");
        }
      } catch (err) {
        // ignore bad payloads
      }
      return;
    }
    if (term) {
      term.write(new Uint8Array(event.data));
    }
  };

  socket.onerror = () => {
    setStatus("Connection error");
    // Don't flash here, onclose will handle retry or final error
  };

  socket.onclose = () => {
    updateButtons(false);

    if (intentionalDisconnect) {
      setStatus("Disconnected");
      overlayEl?.classList.remove("hidden");
      return;
    }

    // Auto-reconnect logic
    if (reconnectAttempts < 5) {
      const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 10000);
      setStatus(`Reconnecting in ${Math.round(delay / 100)}s...`);
      reconnectAttempts++;
      reconnectTimer = setTimeout(() => {
        connect({ resume: true }); // Always try to resume on reconnect
      }, delay);
    } else {
      setStatus("Disconnected (max retries reached)");
      overlayEl?.classList.remove("hidden");
      flash("Terminal connection lost", "error");
    }
  };
}

function disconnect() {
  intentionalDisconnect = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  teardownSocket();
  setStatus("Disconnected");
  overlayEl?.classList.remove("hidden");
  updateButtons(false);
  if (voiceKeyActive) {
    voiceKeyActive = false;
    voiceController?.stop();
  }
}

function sendVoiceTranscript(text) {
  if (!text) {
    flash("Voice capture returned no transcript", "error");
    return;
  }
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    flash("Connect the terminal before using voice input", "error");
    if (voiceStatus) {
      voiceStatus.textContent = "Connect to send voice";
      voiceStatus.classList.remove("hidden");
    }
    return;
  }
  const payload = text.endsWith("\n") ? text : `${text}\n`;
  socket.send(textEncoder.encode(payload));
  term?.focus();
  flash("Voice transcript sent to terminal");
}

function initTerminalVoice() {
  voiceBtn = document.getElementById("terminal-voice");
  voiceStatus = document.getElementById("terminal-voice-status");
  mobileVoiceBtn = document.getElementById("terminal-mobile-voice");

  // Initialize desktop toolbar voice button
  if (voiceBtn && voiceStatus) {
    initVoiceInput({
      button: voiceBtn,
      input: null,
      statusEl: voiceStatus,
      onTranscript: sendVoiceTranscript,
      onError: (msg) => {
        if (!msg) return;
        flash(msg, "error");
        voiceStatus.textContent = msg;
        voiceStatus.classList.remove("hidden");
      },
    })
      .then((controller) => {
        if (!controller) {
          voiceBtn.closest(".terminal-voice")?.classList.add("hidden");
          return;
        }
        voiceController = controller;
        if (voiceStatus) {
          const base = voiceStatus.textContent || "Hold to talk";
          voiceStatus.textContent = `${base} (Alt+V)`;
          voiceStatus.classList.remove("hidden");
        }
        window.addEventListener("keydown", handleVoiceHotkeyDown);
        window.addEventListener("keyup", handleVoiceHotkeyUp);
        window.addEventListener("blur", () => {
          if (voiceKeyActive) {
            voiceKeyActive = false;
            voiceController?.stop();
          }
        });
      })
      .catch((err) => {
        console.error("Voice init failed", err);
        flash("Voice capture unavailable", "error");
        voiceStatus.textContent = "Voice unavailable";
        voiceStatus.classList.remove("hidden");
      });
  }

  // Initialize mobile voice button (no status element - more compact)
  if (mobileVoiceBtn) {
    initVoiceInput({
      button: mobileVoiceBtn,
      input: null,
      statusEl: null,
      onTranscript: sendVoiceTranscript,
      onError: (msg) => {
        if (!msg) return;
        flash(msg, "error");
      },
    })
      .then((controller) => {
        if (!controller) {
          mobileVoiceBtn.classList.add("hidden");
          return;
        }
        mobileVoiceController = controller;
      })
      .catch((err) => {
        console.error("Mobile voice init failed", err);
        mobileVoiceBtn.classList.add("hidden");
      });
  }
}

function matchesVoiceHotkey(event) {
  return event.key && event.key.toLowerCase() === "v" && event.altKey;
}

function handleVoiceHotkeyDown(event) {
  if (!voiceController || voiceKeyActive) return;
  if (!matchesVoiceHotkey(event)) return;
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    flash("Connect the terminal before using voice input", "error");
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  voiceKeyActive = true;
  voiceController.start();
}

function handleVoiceHotkeyUp(event) {
  if (!voiceKeyActive) return;
  if (event && matchesVoiceHotkey(event)) {
    event.preventDefault();
    event.stopPropagation();
  }
  voiceKeyActive = false;
  voiceController?.stop();
}

export function initTerminal() {
  statusEl = document.getElementById("terminal-status");
  overlayEl = document.getElementById("terminal-overlay");
  connectBtn = document.getElementById("terminal-connect");
  disconnectBtn = document.getElementById("terminal-disconnect");
  resumeBtn = document.getElementById("terminal-resume");

  if (!statusEl || !connectBtn || !disconnectBtn || !resumeBtn) return;

  connectBtn.addEventListener("click", () => connect({ resume: false }));
  resumeBtn.addEventListener("click", () => connect({ resume: true }));
  disconnectBtn.addEventListener("click", disconnect);
  updateButtons(false);
  setStatus("Disconnected");

  window.addEventListener("resize", handleResize);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", scheduleResizeAfterLayout);
    window.visualViewport.addEventListener("scroll", scheduleResizeAfterLayout);
  }

  // Initialize mobile touch controls
  initMobileControls();
  initTerminalVoice();
  initTextInputPanel();

  // Auto-connect if session ID exists
  if (localStorage.getItem("codex_terminal_session_id")) {
    connect({ resume: true });
  }
}
