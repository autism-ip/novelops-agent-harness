/**
 * [INPUT]: 依赖环境变量 SESSION_SECRET（必需，运行时校验）
 * [OUTPUT]: signToken / verifyToken — HMAC-SHA256 签名与验证
 * [POS]: api 模块的 session 签名层，被 route.ts 代理守卫消费
 * [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
 */

const SECRET = process.env.SESSION_SECRET || "";

const encoder = new TextEncoder();

function requireSecret(): string {
  if (!SECRET) {
    throw new Error(
      "SESSION_SECRET environment variable is required (min 32 chars)"
    );
  }
  if (SECRET.length < 32) {
    throw new Error(
      "SESSION_SECRET must be at least 32 characters"
    );
  }
  return SECRET;
}

async function hmacKey(): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(requireSecret()),
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

  let sigBytes: Uint8Array<ArrayBuffer>;
  try {
    const decoded = atob(sigB64.replace(/-/g, "+").replace(/_/g, "/"));
    const bytes = new Uint8Array(decoded.length);
    for (let i = 0; i < decoded.length; i++) {
      bytes[i] = decoded.charCodeAt(i);
    }
    sigBytes = bytes;
  } catch {
    return null;
  }

  const key = await hmacKey();

  let valid: boolean;
  try {
    valid = await crypto.subtle.verify(
      "HMAC",
      key,
      sigBytes,
      encoder.encode(payload)
    );
  } catch {
    return null;
  }

  return valid ? payload : null;
}
