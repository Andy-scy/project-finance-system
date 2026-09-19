// 统一 API 封装：/api 前缀，错误统一抛出中文消息
async function request(method, url, body, isForm = false) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    if (isForm) {
      opts.body = body // FormData
    } else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const res = await fetch('/api' + url, opts)
  if (!res.ok) {
    let msg = res.statusText
    try {
      const j = await res.json()
      msg = j.detail || j.error || (typeof j === 'string' ? j : JSON.stringify(j))
    } catch { /* ignore */ }
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res.text()
}

export const api = {
  get: (url) => request('GET', url),
  post: (url, body) => request('POST', url, body),
  put: (url, body) => request('PUT', url, body),
  del: (url) => request('DELETE', url),
  upload: (url, formData) => request('POST', url, formData, true),
}

// 金额展示：元 → 千分位字符串
export function money(v, { dash = '—' } = {}) {
  if (v === null || v === undefined || isNaN(v)) return dash
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 大金额：万元（KPI 用）
export function moneyWan(v, { dash = '—' } = {}) {
  if (v === null || v === undefined || isNaN(v)) return dash
  const wan = Number(v) / 10000
  return wan.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function pct(v, { dash = '—', digits = 1 } = {}) {
  if (v === null || v === undefined || isNaN(v)) return dash
  return Number(v).toFixed(digits) + '%'
}

export function dateCn(iso) {
  if (!iso) return '—'
  return iso
}

export function todayIso() {
  return new Date().toISOString().slice(0, 10)
}
