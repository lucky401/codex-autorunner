const hasWindow = typeof window !== "undefined" && typeof window.location !== "undefined";
const pathname = hasWindow ? window.location.pathname : "";
const repoMatch = pathname.match(/^\/repos\/([^/]+)/);

export const REPO_ID = repoMatch ? repoMatch[1] : null;
export const BASE_PATH = repoMatch ? `/repos/${repoMatch[1]}` : "";

let mode = repoMatch ? "repo" : "unknown";

export async function detectContext() {
  if (mode !== "unknown") {
    return { mode, repoId: REPO_ID };
  }
  if (!hasWindow || typeof fetch !== "function") {
    mode = "repo";
    return { mode, repoId: REPO_ID };
  }
  try {
    const res = await fetch("/hub/repos");
    mode = res.ok ? "hub" : "repo";
  } catch (err) {
    mode = "repo";
  }
  return { mode, repoId: REPO_ID };
}
