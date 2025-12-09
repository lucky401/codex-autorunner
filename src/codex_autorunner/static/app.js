import { initTabs } from "./tabs.js";
import { initDashboard } from "./dashboard.js";
import { initDocs } from "./docs.js";
import { initLogs } from "./logs.js";
import { initTerminal } from "./terminal.js";
import { loadState } from "./state.js";

initTabs();
initDashboard();
initDocs();
initLogs();
initTerminal();

loadState();
