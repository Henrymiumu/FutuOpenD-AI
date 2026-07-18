const BASE = import.meta.env.VITE_API_BASE || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })
  const text = await res.text()
  let data
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { detail: text }
  }
  if (!res.ok) {
    const msg = data?.detail || data?.error || res.statusText || 'Request failed'
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  return data
}

export const api = {
  health: () => request('/api/health'),
  opendStatus: () => request('/api/opend/status'),
  opendConfig: (host, port) =>
    request('/api/opend/config', {
      method: 'POST',
      body: JSON.stringify({ host, port: Number(port) }),
    }),
  snapshot: (codes) =>
    request('/api/market/snapshot', {
      method: 'POST',
      body: JSON.stringify({ codes }),
    }),
  kline: (code, num = 30, ktype = 'K_DAY') =>
    request('/api/market/kline', {
      method: 'POST',
      body: JSON.stringify({ code, num, ktype }),
    }),
  providers: () => request('/api/ai/providers'),
  testAi: (ai) =>
    request('/api/ai/test', {
      method: 'POST',
      body: JSON.stringify({ ai }),
    }),
  analyze: (payload) =>
    request('/api/ai/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
