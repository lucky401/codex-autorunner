import { flash } from "./utils.js";
import { CONSTANTS } from "./constants.js";

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

const textEncoder = new TextEncoder();

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
    fontFamily: '"JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
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

  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const query = resume ? "?mode=resume" : "";
  socket = new WebSocket(`${proto}://${window.location.host}${CONSTANTS.API.TERMINAL_ENDPOINT}${query}`);
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
        if (payload.type === "exit") {
          term?.write(`\r\n[session ended${payload.code !== null ? ` (code ${payload.code})` : ""}] \r\n`);
          // Treat exit as an intentional disconnect or at least not something to auto-reconnect to immediately
          intentionalDisconnect = true; 
          disconnect();
        } else if (payload.type === "error") {
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
}
