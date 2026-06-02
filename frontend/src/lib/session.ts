/**
 * [INPUT]: 依赖环境变量 SESSION_SECRET
 * [OUTPUT]: signToken / verifyToken — HMAC-SHA256 签名与验证
 * [POS]: api 模块的 session 签名层，被 route.ts 代理守卫消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

const SECRET = process.env.SESSION_SECRET || "";

const encoder = new TextEncoder();

async function hmacKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

/**
 * Sign a payload string, returning "payload.signature" format.
 */
export async function signToken(payload: string): Promise<string> {
  const key = await hmacKey();
  const sigBuf = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(payload)
  );
  const sig = btoa(String.fromCharCode(...new Uint8Array(sigBuf)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${payload}.${sig}`;
}

/**
 * Verify a signed token. Returns the payload if valid, null otherwise.
 */
export async function verifyToken(token: string): Promise<string | null> {
  const dot = token.lastIndexOf(".");
  if (dot <= 0) return null;

  const payload = token.slice(0, dot);
  const sigB64 = token.slice(dot + 1);

  const key = await hmacKey();
  const sigBytes = Uint8Array.from(
    atob(sigB64.replace(/-/g, "+").replace(/_/g, "/")),
    (c) => c.charCodeAt(0)
  );

  const valid = await crypto.subtle.verify(
    "HMAC",
    key,
    sigBytes,
    encoder.encode(payload)
  );

  return valid ? payload : null;
}
