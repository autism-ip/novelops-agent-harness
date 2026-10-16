/**
 * [INPUT]: 依赖 app/api/[...path]/route.ts 的服务端代理（注入 x-api-key）
 * [OUTPUT]: 对外提供 ApiError、涵盖响应正文的默认十秒请求及可指定限时的 GET/POST
 * [POS]: api 模块的 HTTP 通信层，被所有业务 hook 消费；浏览器端走服务端代理，不携带 API key
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

// ----------------------------------------------------------------
// ApiError — typed HTTP error wrapper
// ----------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown
  ) {
    super(`API error ${status}`)
    this.name = "ApiError"
  }
}

// ----------------------------------------------------------------
// ApiClient — factory for GET / POST helpers
// ----------------------------------------------------------------

type ApiClientOptions = {
  baseUrl: string
  apiKey?: string
}

export function createApiClient({ baseUrl, apiKey }: ApiClientOptions) {
  async function request<T>(
    path: string,
    options?: RequestInit,
    timeoutMs = 10_000
  ): Promise<T> {
    const url = `${baseUrl}${path}`
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...(apiKey ? { "x-api-key": apiKey } : {}),
    }

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const res = await fetch(url, {
        ...options,
        headers: { ...headers, ...options?.headers },
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new ApiError(
          res.status,
          await res.json().catch((error: unknown) => {
            if (error instanceof DOMException && error.name === "AbortError") throw error;
            return res.statusText;
          })
        )
      }

      return await res.json() as T
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError(0, "Request timeout")
      }
      throw error
    } finally {
      clearTimeout(timeout)
    }
  }

  return {
    get: <T>(path: string, timeoutMs?: number) => request<T>(path, undefined, timeoutMs),
    post: <T>(path: string, body: unknown, timeoutMs?: number) =>
      request<T>(path, { method: "POST", body: JSON.stringify(body) }, timeoutMs),
  }
}

// ----------------------------------------------------------------
// Default singleton — browser client uses rewrite proxy, no API key
// ----------------------------------------------------------------

export const api = createApiClient({
  baseUrl: "",
})
