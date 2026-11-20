const { test } = require('node:test');
const assert = require('node:assert/strict');
const { resample, ema20, movingAverage, contiguous } = require('./chart-data.ts');
const start = Date.parse('2026-11-19T09:15:00+05:30');
const iso = minute => new Date(start + minute * 60000).toISOString();
const session = (open = 0, close = 375) => ({ opens_at: iso(open), closes_at: iso(close), verified: true });
function data(count = 25) {
  return { start: iso(0), end: iso(375), as_of: iso(400), sessions: [session()], gaps: [], unknown_session_dates: [], truncated: false,
    bars: Array.from({ length: count }, (_, i) => ({ opens_at: iso(i), open: String(i + 1), high: String(i + 3), low: String(i), close: String(i + 2), volume: 10, state: 'closed', source: 'angelone-historical:getCandleData' })) };
}

test('5/15-minute bars align to the verified session, with OHLC and non-duplicated volume', () => {
  const input = data(30), output = resample(input, 5);
  assert.equal(resample(input, 1), input);
  assert.equal(output.bars.length, 6);
  assert.deepEqual(output.bars[0], { opens_at: iso(0), open: '1', high: '7', low: '0', close: '6', volume: 50, state: 'elapsed', source: 'derived_broker_history' });
  assert.equal(resample(input, 15).bars.length, 2);
  const special = { ...input, sessions: [session(2, 12)] };
  assert.deepEqual(resample(special, 5).bars.map(bar => bar.opens_at), [iso(2), iso(7)]);
  assert.equal(input.bars[0].volume, 10); // No mutation of cached inputs.
});

test('missing minutes suppress the whole larger bar; unknown volume never becomes zero', () => {
  const input = data(10);
  input.bars.splice(2, 1);
  input.bars[5].volume = null;
  input.bars[5].source = 'observed_ltp_snapshots';
  const result = resample(input, 5);
  assert.deepEqual(result.bars.map(bar => bar.opens_at), [iso(5)]);
  assert.equal(result.bars[0].volume, null);
  assert.equal(result.bars[0].source, 'derived_mixed');
  assert.ok(result.gaps.includes(iso(0)));
});

test('forming bars, shortened sessions, query boundaries and unverified sessions stay explicit', () => {
  const input = data(7);
  input.end = iso(6); input.as_of = new Date(start + 6.5 * 60000).toISOString();
  const bars = resample(input, 5).bars;
  assert.equal(bars[1].state, 'provisional');
  assert.equal(bars[1].volume, 20);
  input.sessions = [session(0, 7)]; input.as_of = iso(8);
  assert.equal(resample(input, 5).bars[1].state, 'elapsed');
  input.end = iso(5);
  assert.equal(resample(input, 5).bars.length, 1); // A sliced interval is not a complete bar.
  input.sessions[0].verified = false;
  assert.deepEqual(resample(input, 5).bars, []);
});

test('EMA uses the declared SMA seed and recursive formula, with no provisional point', () => {
  const input = data(22);
  input.bars[21].state = 'provisional';
  const ema = ema20(input, 1);
  assert.equal(ema.length, 2);
  assert.equal(ema[0].value, 11.5);
  assert.equal(ema[1].value, 12.5);
  assert.equal(ema[0].time, Date.parse(iso(19)) / 1000);
  assert.deepEqual(ema20(data(19), 1), []);
});

test('EMA and plotted line segments reset across gaps and sessions', () => {
  const input = data(42);
  input.bars.splice(20, 1);
  const ema = ema20(input, 1);
  assert.deepEqual(ema.map(point => point.time), [19, 40, 41].map(minute => Date.parse(iso(minute)) / 1000));
  assert.equal(contiguous(ema, 1).length, 2);
  input.sessions = [session(0, 20), session(21, 42)];
  assert.equal(ema20(input, 1).length, 3);
  assert.equal(ema20(resample(data(30), 5), 5).length, 0);
});


test('configurable SMA rolls equally weighted closes; EMA uses selected-period seed and smoothing', () => {
  const input = data(5);
  input.bars.forEach((bar, index) => { bar.close = String([2, 4, 8, 10, 20][index]); });
  movingAverage(input, 1, 'SMA', 3).forEach((point, index) => assert.ok(Math.abs(point.value - [14 / 3, 22 / 3, 38 / 3][index]) < 1e-12));
  const ema = movingAverage(input, 1, 'EMA', 3);
  assert.equal(ema[0].value, 14 / 3);
  assert.ok(Math.abs(ema[1].value - 22 / 3) < 1e-12);
  assert.ok(Math.abs(ema[2].value - 41 / 3) < 1e-12);
  assert.deepEqual(movingAverage(input, 1, 'SMA', 9), []);
  for (const period of [0, 1, 2.5, 201, NaN, Infinity]) assert.throws(() => movingAverage(input, 1, 'EMA', period), RangeError);
});

test('selected studies exclude forming closes and restart after gaps and verified sessions', () => {
  const input = data(10);
  input.bars[3].state = 'provisional';
  input.bars.splice(7, 1);
  for (const kind of ['EMA', 'SMA']) {
    assert.deepEqual(movingAverage(input, 1, kind, 3).map(p => p.time), [2, 6].map(i => Date.parse(iso(i)) / 1000));
    input.sessions = [session(0, 2), session(2, 10)];
    assert.deepEqual(movingAverage(input, 1, kind, 3).map(p => p.time), [6].map(i => Date.parse(iso(i)) / 1000));
    input.sessions = [session()];
  }
});

test('device preferences validate every field and ignore unrelated stored data', () => {
  const { parseChartPreferences, DEFAULT_CHART_PREFERENCES } = require('./chart-preferences.ts');
  for (const raw of [null, '{', 'null', '[]', '1']) assert.deepEqual(parseChartPreferences(raw), DEFAULT_CHART_PREFERENCES);
  assert.deepEqual(parseChartPreferences(JSON.stringify({ minutes: 15, mode: 'line', showAverage: true, averageKind: 'SMA', averagePeriod: 50, token: 'ignored-fixture' })),
    { minutes: 15, mode: 'line', showAverage: true, averageKind: 'SMA', averagePeriod: 50 });
  assert.deepEqual(parseChartPreferences(JSON.stringify({ minutes: 60, mode: 'bad', showAverage: 'true', averageKind: 'bad', averagePeriod: '20' })), DEFAULT_CHART_PREFERENCES);
});
