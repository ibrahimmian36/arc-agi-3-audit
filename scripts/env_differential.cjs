/**
 * Edge-by-edge differential for an environment level model.
 * Argv: oraclePath edgesPath moduleName
 * edges file: {nodes:[{i,status,abs:{cx,cy,rot,lives,steps,status}}], edges:[[src,action,dst],...]}
 * For every edge, apply the MODEL's transition to the source's abstract state
 * and compare with the destination's abstract state recorded from the SHIPPED
 * game. Stdout LAST line: __DIFF__{loaded, rows:[{edge, agree, why, model, shipped}], n}
 */
const fs = require("fs"); const path = require("path");
function main() {
  const [oraclePath, edgesPath, modName] = process.argv.slice(2);
  const realLog = console.log; const silent = () => {};
  console.log = silent; console.error = silent; console.warn = silent; console.info = silent;
  let oracle = null, err = null;
  try { oracle = require(path.resolve(oraclePath)); } catch (e) { err = String(e && e.message).slice(0, 160); }
  if (!oracle || !oracle[modName] || !oracle._dafny) { realLog("__DIFF__" + JSON.stringify({ loaded: false, error: err || "module missing", rows: [] })); return; }
  const BigNumber = require(path.resolve(path.dirname(oraclePath), "node_modules", "bignumber.js"));
  const M = oracle[modName].__default;
  const g = JSON.parse(fs.readFileSync(edgesPath, "utf8"));
  const code = (s) => s === "PLAY" ? 0 : s === "WIN" ? 1 : 2;
  const num = (b) => Number(b.toString());
  const rows = []; let disagreements = 0, winEdges = 0;
  for (const [src, a, dst] of g.edges) {
    const s = g.nodes[src].abs, t = g.nodes[dst].abs;
    let model = null, why = "";
    try {
      const r = M.Apply(new BigNumber(s.cx), new BigNumber(s.cy), new BigNumber(s.rot), new BigNumber(s.lives), new BigNumber(s.steps), new BigNumber(code(s.status)), new BigNumber(a));
      model = { cx: num(r.dtor_x), cy: num(r.dtor_y), rot: num(r.dtor_rot), lives: num(r.dtor_lives), steps: num(r.dtor_steps), status: num(M.StatusCode(r)) };
    } catch (e) { why = "model threw: " + String(e && e.message).slice(0, 100); }
    const shipped = { cx: t.cx, cy: t.cy, rot: t.rot, lives: t.lives, steps: t.steps, status: code(t.status) };
    // A lost-life or GAME_OVER transition is compared on lives/status/position; the
    // shipped game reports lives=0 only via GAME_OVER.
    // Scope: the model covers ONE level. On a transition both sides call a WIN,
    // the shipped game has already loaded the next level (its start position,
    // steps and lives), which is outside the model; such edges are compared on
    // status only and counted separately.
    let agree, winEdge = model !== null && model.status === 1 && shipped.status === 1;
    if (winEdge) { agree = true; winEdges++; }
    else {
      agree = model !== null && ["cx", "cy", "rot", "lives", "steps", "status"].every((k) => model[k] === shipped[k]);
      if (model !== null && !agree) why = ["cx", "cy", "rot", "lives", "steps", "status"].filter((k) => model[k] !== shipped[k]).join(",");
    }
    if (!agree) disagreements++;
    if (!agree || rows.length < 5) rows.push({ src, a, dst, agree, why, model, shipped, from: s });
  }
  realLog("__DIFF__" + JSON.stringify({ loaded: true, n: g.edges.length, disagreements, win_edges_status_only: winEdges, rows }));
}
try { main(); } catch (e) { process.stdout.write("__DIFF__" + JSON.stringify({ loaded: false, error: String(e && e.message).slice(0, 160), rows: [] }) + "\n"); }
