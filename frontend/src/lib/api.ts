const TOKEN_KEY = "genbi_auth_token"

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export async function login(
  email: string,
  password: string,
): Promise<{ ok: boolean; error?: string }> {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    let detail = "Login fallido"
    try {
      const data = await res.json()
      if (data.error) detail = data.error
      else if (data.detail) detail = data.detail
    } catch {
      /* cuerpo no JSON */
    }
    return { ok: false, error: detail }
  }
  const data = await res.json()
  setToken(data.token)
  return { ok: true }
}

export async function verify(): Promise<boolean> {
  const token = getToken()
  if (!token) return false
  const res = await fetch("/api/verify", {
    headers: { Authorization: `Bearer ${token}` },
  })
  return res.ok
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<{ ok: boolean; status: number; data?: T; error?: string }> {
  const token = getToken()
  const headers = new Headers(init.headers)
  headers.set("Content-Type", "application/json")
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      if (data.error) detail = data.error
      else if (data.detail) detail = data.detail
    } catch {
      /* cuerpo no JSON */
    }
    if (res.status === 401) clearToken()
    return { ok: false, status: res.status, error: detail }
  }
  try {
    const data = (await res.json()) as T
    return { ok: true, status: res.status, data }
  } catch {
    return { ok: true, status: res.status }
  }
}

export interface QueryResponse {
  columns: string[]
  rows: unknown[][]
  row_count: number
  duration_ms: number
}

export interface Nl2SqlResponse extends QueryResponse {
  sql: string
  answer: string
}

export async function runQuery(sql: string): Promise<QueryResponse> {
  const res = await apiFetch<QueryResponse>("/api/v1/query", {
    method: "POST",
    body: JSON.stringify({ sql }),
  })
  if (!res.ok || !res.data) {
    throw new Error(res.error || "consulta fallida")
  }
  return res.data
}

export async function runNl2Sql(question: string): Promise<Nl2SqlResponse> {
  const res = await apiFetch<Nl2SqlResponse>("/api/v1/nl2sql", {
    method: "POST",
    body: JSON.stringify({ question }),
  })
  if (!res.ok || !res.data) {
    throw new Error(res.error || "no se pudo responder")
  }
  return res.data
}
