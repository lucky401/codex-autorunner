import { BASE_PATH, REPO_ID } from "./env.js";

function cachePrefix() {
  const scope = REPO_ID ? `repo:${REPO_ID}` : `base:${BASE_PATH || ""}`;
  return `car:${encodeURIComponent(scope)}:`;
}

function scopedKey(key) {
  return cachePrefix() + key;
}

/**
 * Save data to localStorage with error handling.
 * @param {string} key - The key to store the data under (will be scoped per repo/base path)
 * @param {any} data - The data to store (will be JSON stringified)
 */
export function saveToCache(key, data) {
  try {
    const json = JSON.stringify(data);
    localStorage.setItem(scopedKey(key), json);
  } catch (err) {
    console.warn("Failed to save to cache", key, err);
  }
}

/**
 * Load data from localStorage with error handling.
 * @param {string} key - The key to retrieve data from (will be scoped per repo/base path)
 * @returns {any|null} The parsed data, or null if not found or invalid
 */
export function loadFromCache(key) {
  try {
    const json = localStorage.getItem(scopedKey(key));
    if (!json) return null;
    return JSON.parse(json);
  } catch (err) {
    console.warn("Failed to load from cache", key, err);
    return null;
  }
}

/**
 * Remove data from localStorage.
 * @param {string} key - The key to remove (will be scoped per repo/base path)
 */
export function clearCache(key) {
  try {
    localStorage.removeItem(scopedKey(key));
  } catch (err) {
    console.warn("Failed to clear cache", key, err);
  }
}
