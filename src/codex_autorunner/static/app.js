import { initTabs, registerTab } from "./tabs.js";
import { initDashboard } from "./dashboard.js";
import { initDocs } from "./docs.js";
import { initLogs } from "./logs.js";
import { initTerminal } from "./terminal.js";
import { loadState } from "./state.js";

// Register core tabs
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

