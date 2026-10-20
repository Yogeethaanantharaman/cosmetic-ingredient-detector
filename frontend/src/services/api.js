const CLIENT_KEY = 'inci-sight-client-id';

export function getClientId() {
  try {
    let id = localStorage.getItem(CLIENT_KEY);
    if (!id) {
      id = globalThis.crypto?.randomUUID?.() || `browser-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(CLIENT_KEY, id);
    }
    return id;
  } catch {
    return `session-${Date.now()}`;
  }
}

async function request(path, options = {}, clientId) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { ...options.headers, ...(clientId ? { 'X-Client-ID': clientId } : {}) },
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Could not reach the INCI Sight backend. Check your connection and try again.');
  }
  let data;
  try { data = await response.json(); } catch { throw new Error('The backend returned an unreadable response.'); }
  if (!response.ok) throw new Error(data?.error?.message || data?.detail || `Request failed (${response.status}).`);
  return data;
}

export function getWatchlist(clientId) {
  return request('/api/watchlist', {}, clientId);
}

export function saveWatchlist(ingredients, clientId) {
  return request('/api/watchlist', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ingredients }),
  }, clientId);
}

export async function analyzeImage(file, watchlist, clientId, signal, productName = '') {
  if (!file) throw new Error('Choose a clear photo of the ingredient label first.');
  const body = new FormData();
  body.append('file', file);
  body.append('avoid_list', JSON.stringify(watchlist));
  body.append('product_name', productName);
  return request('/api/analyze', { method: 'POST', body, signal }, clientId);
}

export function reviewText(text, watchlist, clientId, scanId, productName = '') {
  return request('/api/review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, avoid_list: watchlist, scan_id: scanId, product_name: productName }),
  }, clientId);
}

export function getHistory(clientId) {
  return request('/api/history', {}, clientId);
}
