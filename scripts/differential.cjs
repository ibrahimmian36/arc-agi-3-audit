/**
 * Oracle caller for the compiled Dafny scoring model.
 *
 * Argv: oraclePath fixturesPath
 * Stdin: none. Stdout, LAST line, prefixed __DIFF__: {"loaded", "error"?, "rows": [...]}
 *
 * Each fixture: {id, baselines: [nat], actions: [nat], completed: [bool]}.
 * For every fixture the oracle is evaluated under four readings:
 *   prose/nocut, eq/nocut, prose/cut, eq/cut
 * and returns the environment score and per-level scores as exact rationals
 * (num/den strings) and as decimals scaled to 0..132.25 (12 places).
 *
 * Hygiene (pattern from intentio/phase1/refloop/differential.cjs): the oracle's
 * console is silenced before it loads, output is a single marker line so any
 * stdout pollution cannot break the parse, and the caller runs this under a
 * scrubbed environment with a timeout.
 */
const fs = require("fs");
const path = require("path");

function main() {
  const [oraclePath, fixturesPath] = process.argv.slice(2);
  const realLog = console.log;
  const silent = () => {};
  console.log = silent; console.error = silent; console.warn = silent; console.info = silent; console.debug = silent;
  let oracle = null, loadError = null;
  try { oracle = require(path.resolve(oraclePath)); }
  catch (e) { loadError = String(e && e.message).slice(0, 160); }
  if (!oracle || !oracle.Scoring || !oracle._dafny) {
    realLog("__DIFF__" + JSON.stringify({ loaded: false, error: loadError || "oracle lacks Scoring/_dafny", rows: [] }));
    return;
  }
  const _dafny = oracle._dafny;
  const BigNumber = require(path.resolve(path.dirname(oraclePath), "node_modules", "bignumber.js"));
  const S = oracle.Scoring.__default;
  const nat = (n) => new BigNumber(n);
  const seqNat = (xs) => _dafny.Seq.of(...xs.map(nat));
  const seqBool = (xs) => _dafny.Seq.of(...xs.map(Boolean));
  const rat = (r) => {
    // BigRational keeps num/den as BigNumber; reduce and scale by 100 for display.
    const num = r.num, den = r.den;
    const dec = new BigNumber(num.toString()).dividedBy(new BigNumber(den.toString())).multipliedBy(100).toFixed(12);
    return { num: num.toString(), den: den.toString(), pct: dec };
  };
  const fixtures = JSON.parse(fs.readFileSync(fixturesPath, "utf8"));
  const rows = [];
  for (const f of fixtures) {
    const row = { id: f.id, readings: {} };
    for (const [name, prose, cut] of [["prose_nocut", true, false], ["eq_nocut", false, false], ["prose_cut", true, true], ["eq_cut", false, true]]) {
      try {
        const b = seqNat(f.baselines), a = seqNat(f.actions), c = seqBool(f.completed);
        const env = S.EnvScoreFromActions(b, a, c, prose, cut);
        const lv = S.LevelScoresFromActions(b, a, c, prose, cut);
        row.readings[name] = { env: rat(env), levels: Array.from(lv).map(rat) };
      } catch (e) {
        row.readings[name] = { error: String(e && e.message).slice(0, 160) };
      }
    }
    rows.push(row);
  }
  realLog("__DIFF__" + JSON.stringify({ loaded: true, rows }));
}
try { main(); } catch (e) { process.stdout.write("__DIFF__" + JSON.stringify({ loaded: false, error: String(e && e.message).slice(0, 160), rows: [] }) + "\n"); }
