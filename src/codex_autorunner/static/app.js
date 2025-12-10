import { detectContext } from "./env.js";
import { initHub } from "./hub.js";
import { initTabs, registerTab } from "./tabs.js";
import { initDashboard } from "./dashboard.js";
import { initDocs } from "./docs.js";
import { initLogs } from "./logs.js";
import { initTerminal } from "./terminal.js";
import { loadState } from "./state.js";

function initRepoShell() {
  registerTab("dashboard", "Dashboard");
  registerTab("docs", "Docs");
  registerTab("logs", "Logs");
  registerTab("terminal", "Terminal");

  initTabs();
  initDashboard();
  initDocs();
  initLogs();
  initTerminal();

  loadState();
}

async function bootstrap() {
  const { mode } = await detectContext();
  const hubShell = document.getElementById("hub-shell");
  const repoShell = document.getElementById("repo-shell");

  if (mode === "hub") {
    if (hubShell) hubShell.classList.remove("hidden");
    if (repoShell) repoShell.classList.add("hidden");
    initHub();
    return;
  }

  if (repoShell) repoShell.classList.remove("hidden");
  if (hubShell) hubShell.classList.add("hidden");
  initRepoShell();
}

bootstrap();
