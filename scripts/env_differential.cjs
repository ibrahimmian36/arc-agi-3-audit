/**
 * Edge-by-edge differential for an environment level model, STREAMING.
 *
 * Argv: oraclePath edgesPath moduleName
 * edgesPath: gzipped JSONL, one edge per line:
 *     {"i":srcId,"j":dstId,"a":action,"s":srcVec,"t":dstVec}
 *   vec = [cx, cy, rot, color, shape, lives, steps, status, goalsDone[]]
 *
 * For every edge the MODEL's transition is applied to the source vector and
 * compared with the destination vector recorded from the SHIPPED game. Neither
 * side ever holds the edge list: the file is read line by line and only
 * counters plus a bounded sample of rows are kept.
 *
 * Reject-only. Stdout, LAST line, prefixed __DIFF__.
 */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const readline = require("readline");

const FIELDS = ["cx", "cy", "rot", "lives", "steps", "eaten", "status"];
const MAX_ROWS = 50;

function toState(v) {
  return { cx: v[0], cy: v[1], rot: v[2], color: v[3], shape: v[4], lives: v[5], steps: v[6],
           status: v[7], goals: v[8], eaten: v[9] === undefined ? 0 : v[9] };
}

async function main() {
  const [oraclePath, edgesPath, modName] = process.argv.slice(2);
  const realLog = console.log;
  const silent = () => {};
  console.log = silent; console.error = silent; console.warn = silent; console.info = silent;

  let oracle = null, loadError = null;
  try { oracle = require(path.resolve(oraclePath)); } catch (e) { loadError = String(e && e.message).slice(0, 160); }
  if (!oracle || !oracle[modName] || !oracle._dafny) {
    realLog("__DIFF__" + JSON.stringify({ loaded: false, error: loadError || `module ${modName} missing`, rows: [] }));
    return;
  }
  const BigNumber = require(path.resolve(path.dirname(oraclePath), "node_modules", "bignumber.js"));
  const M = oracle[modName].__default;
  const num = (b) => Number(b.toString());

  let n = 0, disagreements = 0, winEdges = 0, modelErrors = 0;
  const rows = [];
  const stream = readline.createInterface({
    input: fs.createReadStream(edgesPath).pipe(zlib.createGunzip()),
    crlfDelay: Infinity,
  });

  for await (const line of stream) {
    if (!line) continue;
    const e = JSON.parse(line);
    const s = toState(e.s), t = toState(e.t);
    n++;
    let model = null, why = "";
    try {
      const r = M.Apply(new BigNumber(s.cx), new BigNumber(s.cy), new BigNumber(s.rot),
                        new BigNumber(s.lives), new BigNumber(s.steps), new BigNumber(s.eaten),
                        new BigNumber(s.status), new BigNumber(e.a));
      model = { cx: num(r.dtor_x), cy: num(r.dtor_y), rot: num(r.dtor_rot),
                lives: num(r.dtor_lives), steps: num(r.dtor_steps), eaten: num(r.dtor_eaten),
                status: num(M.StatusCode(r)) };
    } catch (err) {
      why = "model threw: " + String(err && err.message).slice(0, 100);
      modelErrors++;
    }
    // Scope: the model covers ONE level. Where both sides call a WIN the shipped
    // game has already loaded the NEXT level (its start cell, steps and lives),
    // which is outside the model; such edges are compared on status only and
    // counted separately.
    let agree;
    if (model !== null && model.status === 1 && t.status === 1) { agree = true; winEdges++; }
    else {
      agree = model !== null && FIELDS.every((k) => model[k] === t[k]);
      if (model !== null && !agree) why = FIELDS.filter((k) => model[k] !== t[k]).join(",");
    }
    if (!agree) {
      disagreements++;
      if (rows.length < MAX_ROWS) rows.push({ i: e.i, j: e.j, a: e.a, why, from: s, model, shipped: t });
    }
  }
  realLog("__DIFF__" + JSON.stringify({ loaded: true, n, disagreements, win_edges_status_only: winEdges, model_errors: modelErrors, rows }));
}

main().catch((e) => {
  process.stdout.write("__DIFF__" + JSON.stringify({ loaded: false, error: String(e && e.message).slice(0, 160), rows: [] }) + "\n");
});
