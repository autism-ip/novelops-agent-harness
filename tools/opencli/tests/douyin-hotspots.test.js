import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchHotspots, ENDPOINT } from '../douyin-hotspots.js';

async function withFetch(response, run) {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(url, ENDPOINT);
    assert.equal(options.redirect, 'error');
    assert.equal(options.credentials, 'omit');
    assert.ok(options.signal);
    if (response instanceof Error) throw response;
    return response;
  };
  try { await run(); } finally { globalThis.fetch = original; }
}

test('public feed maps actual fields and respects requested limit', async () => {
  const word_list = Array.from({length: 50}, (_, i) => ({word: `topic${i}`, hot_value: 500-i, label: 3}));
  await withFetch(Response.json({status_code: 0, word_list, active_time: 'source time'}), async () => {
    const rows = await fetchHotspots({limit: 35});
    assert.equal(rows.length, 35);
    assert.equal(rows[0].title, 'topic0');
    assert.equal(rows[0].heat_value, 500);
    assert.equal(rows[34].rank, 35);
    assert.equal(rows[0].url, ENDPOINT);
    assert.equal(rows[0].raw_json.word, 'topic0');
    assert.equal(rows[0].raw_json.active_time, 'source time');
    assert.equal(rows[0].source, 'douyin');
  });
});

test('short public feeds are not padded', async () => {
  await withFetch(Response.json({status_code: 0, word_list: [{word: 'one', hot_value: 2}]}), async () => {
    assert.equal((await fetchHotspots({limit: 50})).length, 1);
  });
});

test('invalid limits never reach the network', async () => {
  for (const limit of [0, 51, 1.5, 'bad']) {
    await assert.rejects(fetchHotspots({limit}), error => error.code === 'ARGUMENT');
  }
});

test('schema changes and upstream errors fail explicitly', async () => {
  for (const payload of [{}, {status_code: 1, word_list: []}, {status_code: 0, word_list: [{word: 4}]},
    {status_code: 0, word_list: [{word: 'title', hot_value: -1}]}]) {
    await withFetch(Response.json(payload), async () => {
      await assert.rejects(fetchHotspots({}), error => error.code === 'COMMAND_EXEC');
    });
  }
});

test('empty feed is distinguished from schema failure', async () => {
  await withFetch(Response.json({status_code: 0, word_list: []}), async () => {
    await assert.rejects(fetchHotspots({}), error => error.code === 'EMPTY_RESULT');
  });
});

test('HTTP and malformed JSON failures are typed', async () => {
  for (const response of [new Response('bad', {status: 503}), new Response('not-json')]) {
    await withFetch(response, async () => {
      await assert.rejects(fetchHotspots({}), error => error.code === 'COMMAND_EXEC');
    });
  }
});

test('timeouts and transport failures are sanitized', async () => {
  for (const [error, code] of [[new DOMException('private', 'TimeoutError'), 'TIMEOUT'], [new Error('private'), 'COMMAND_EXEC']]) {
    await withFetch(error, async () => {
      await assert.rejects(fetchHotspots({}), actual => actual.code === code && !actual.message.includes('private'));
    });
  }
});
