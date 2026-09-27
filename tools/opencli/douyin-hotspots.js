// Strategy: PUBLIC_API, read-only; undocumented upstream schema, fail on drift.
// Evidence: unauthenticated Node fetch returned HTTP 200/status_code=0/50 word_list
// rows on 2026-09-28. No cookies, browser bridge, signing, or configurable target.
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError, CommandExecutionError, EmptyResultError, TimeoutError } from '@jackwener/opencli/errors';

export const ENDPOINT = 'https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/';

export async function fetchHotspots(args) {
  const limit = Number(args.limit ?? 50);
  if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
    throw new ArgumentError('limit must be an integer from 1 to 50');
  }
  let response;
  let payload;
  try {
    response = await fetch(ENDPOINT, {
      signal: AbortSignal.timeout(10000), redirect: 'error', credentials: 'omit',
    });
    if (!response.ok) throw new CommandExecutionError(`Public feed HTTP ${response.status}`);
    payload = await response.json();
  } catch (error) {
    if (error?.name === 'TimeoutError' || error?.name === 'AbortError') {
      throw new TimeoutError('Public Douyin feed', 10);
    }
    throw new CommandExecutionError('Public Douyin feed request or JSON failed');
  }
  if (payload?.status_code !== 0 || !Array.isArray(payload.word_list)) {
    throw new CommandExecutionError('Public Douyin feed schema or status changed');
  }
  if (!payload.word_list.length) throw new EmptyResultError('novelops douyin-hotspots', 'Public feed is empty');
  const captured = new Date().toISOString();
  return payload.word_list.slice(0, limit).map((item, index) => {
    if (typeof item?.word !== 'string' || !item.word.trim() ||
        !Number.isSafeInteger(item.hot_value) || item.hot_value < 0) {
      throw new CommandExecutionError('Public Douyin feed row schema changed');
    }
    return {
      source: 'douyin', rank: index + 1, title: item.word, url: ENDPOINT,
      heat_value: item.hot_value, category: String(item.label ?? ''), captured_at: captured,
      raw_json: {...item, active_time: payload.active_time ?? null},
    };
  });
}

cli({
  site: 'novelops', name: 'douyin-hotspots', access: 'read',
  description: 'Fetch the public Douyin word billboard without browser credentials',
  domain: 'www.iesdouyin.com', strategy: Strategy.PUBLIC, browser: false,
  args: [{name: 'limit', type: 'int', default: 50, help: 'Maximum rows (1–50); short feeds are not padded'}],
  columns: ['source', 'rank', 'title', 'url', 'heat_value', 'category', 'captured_at', 'raw_json'],
  func: fetchHotspots,
});
