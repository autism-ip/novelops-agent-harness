/**
 * [INPUT]: 依赖环境变量 NEXT_PUBLIC_API_BASE_URL, NEXT_PUBLIC_API_KEY
 * [OUTPUT]: 对外提供 ApiError 类、createApiClient 工厂函数、api 默认实例
 * [POS]: api 模块的 HTTP 通信层，被所有业务 hook 消费
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
    options?: RequestInit
  ): Promise<T> {
    const url = `${baseUrl}${path}`
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...(apiKey ? { "x-api-key": apiKey } : {}),
    }

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 10_000)

    try {
      const res = await fetch(url, {
        ...options,
        headers: { ...headers, ...options?.headers },
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new ApiError(
          res.status,
          await res.json().catch(() => res.statusText)
        )
      }

      return res.json() as Promise<T>
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
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body: unknown) =>
      request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  }
}

// ----------------------------------------------------------------
// Default singleton — consumed by hooks & server components
// ----------------------------------------------------------------

export const api = createApiClient({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  apiKey: process.env.NEXT_PUBLIC_API_KEY,
})
