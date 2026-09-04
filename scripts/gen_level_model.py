"""Generate model/<game>_level<k>.dfy from artifacts/env/<game>/level<k>.json.

CONSTANTS come from the JSON, which is read out of the shipped level object by
scripts/extract_level.py. Never by hand.

RULES are hand-written from reading the shipped ls20 source at the rule level
(`step`, `txnfzvzetn`, `on_set_level`, the step-counter display class):

  * a wall blocks and ends the collision scan;
  * the goal blocks unless the piece matches, and a mismatch "flashes";
  * a flash consumes the action at no step cost;
  * on level 1 ONLY, cycling a modifier tile into a match also flashes
    (`vqfjzzkhid` returns False when `level_index > 0`);
  * an energy pickup refills the counter to full and, because it short-circuits
    the `not yubyobdoss and not mfyzdfvxsm()` test, skips that move's decrement
    entirely; it is restored when a life is lost;
  * any other move, blocked or not, costs one decrement;
  * completing the goals is checked BEFORE the life-loss branch, so a final
    move that both wins and exhausts the counter is a win;
  * exhausting the counter costs a life and restores the level's start layout;
    losing the last life ends the game.

The generator REFUSES rather than guesses: a level using a mechanic not modelled
here fails loudly with the reason. Extend the guard and the rules together.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Unsupported(SystemExit):
    pass


def guard(d: dict, level: int) -> None:
    why = []
    if d["pushers"]:
        why.append(f"{len(d['pushers'])} pusher(s) (moving walls that shove the player)")
    if d["patrol"]:
        why.append(f"{len(d['patrol'])} patrol area(s)")
    if d["color_tiles"]:
        why.append(f"{len(d['color_tiles'])} colour tile(s)")
    if d["shape_tiles"]:
        why.append(f"{len(d['shape_tiles'])} shape tile(s)")
    if d["fog"]:
        why.append("fog")
    if len(d["goals"]) != 1:
        why.append(f"{len(d['goals'])} goals (the model handles exactly one)")
    if len(d["rotation_tiles"]) != 1:
        why.append(f"{len(d['rotation_tiles'])} rotation tiles (the model handles exactly one)")
    if not why and len(d["goals"]) == 1:
        g = d["goals"][0]
        # With no colour or shape tile the piece's colour and shape never change,
        # so the goal test reduces to rotation -- but only if they already match.
        if g["shape_index"] != d["start_shape_index"]:
            why.append(f"start shape {d['start_shape_index']} != goal shape {g['shape_index']} with no shape tile")
        if g["color_value"] != d["start_color_value"]:
            why.append(f"start colour {d['start_color_value']} != goal colour {g['color_value']} with no colour tile")
    if why:
        raise Unsupported(f"level {level} uses mechanics this generator does not model: " + "; ".join(why))


def wall_pred(walls: list[list[int]]) -> str:
    return "\n    || ".join(f"(x == {x} && y == {y})" for x, y in walls)


def energy_index(energy: list[list[int]]) -> str:
    if not energy:
        return "  function EnergyIndex(x: int, y: int): int { -1 }\n"
    lines = ["  // Index of the energy pickup on this cell, or -1.",
             "  function EnergyIndex(x: int, y: int): int",
             f"    ensures -1 <= EnergyIndex(x, y) < {len(energy)}",
             "  {"]
    body = " else ".join(f"if x == {c[0]} && y == {c[1]} then {i}" for i, c in enumerate(energy))
    lines.append(f"    {body} else -1")
    lines.append("  }")
    return "\n".join(lines) + "\n"


def mask_ops(ne: int) -> str:
    """Explicit operations over the energy bitmask. The mask space has 2^NE
    elements with NE at most a handful, so legality is a literal disjunction and
    every lemma about it is decided by case analysis. Deliberately not Pow2
    arithmetic: that form put Dafny into nonlinear reasoning and timed out, and
    a timed-out obligation is unknown, not discharged."""
    masks = " || ".join(f"m == {m}" for m in range(2 ** ne))
    L = [f"  // The {2 ** ne} legal value(s) of the energy bitmask for NE = {ne}.",
         "  predicate EatenLegal(m: nat) { " + masks + " }",
         "",
         "  function AddBit(m: nat, i: int): nat",
         "    requires 0 <= i < NE",
         "  {"]
    if ne == 0:
        L.append("    m  // unreachable: the precondition is unsatisfiable when NE == 0")
    else:
        L.append("    " + " else ".join(f"if i == {i} then m + {2 ** i}" for i in range(ne)) + " else m")
    L += ["  }", "",
          "  predicate HasBit(m: nat, i: int)",
          "    requires 0 <= i < NE",
          "  {"]
    if ne == 0:
        L.append("    false  // unreachable: the precondition is unsatisfiable when NE == 0")
    else:
        L.append("    " + " else ".join(f"if i == {i} then (m / {2 ** i}) % 2 == 1" for i in range(ne)) + " else false")
    L.append("  }")
    return "\n".join(L) + "\n"


def border_facts(W: int, H: int) -> str:
    L = ["  // The extracted wall set contains the whole border of the W x H lattice.",
         "  lemma BorderFacts()",
         "    ensures forall x :: 0 <= x < W ==> IsWall(x, 0) && IsWall(x, H - 1)",
         "    ensures forall y :: 0 <= y < H ==> IsWall(0, y) && IsWall(W - 1, y)",
         "  {",
         "    forall x | 0 <= x < W ensures IsWall(x, 0) && IsWall(x, H - 1) {",
         "      " + " else ".join(f"if x == {x} {{ }}" for x in range(W)),
         "    }",
         "    forall y | 0 <= y < H ensures IsWall(0, y) && IsWall(W - 1, y) {",
         "      " + " else ".join(f"if y == {y} {{ }}" for y in range(H)),
         "    }",
         "  }"]
    return "\n".join(L) + "\n"


def nested_step(witness: list[int]) -> str:
    """Step(Step(... Step(Start(), a0) ..., a_{n-1})) as a single ground term."""
    expr = "Start()"
    for a in witness:
        expr = f"Step({expr}, {a})"
    return expr


CHUNK = 10


def _state_lit(st: list) -> str:
    return f"S({st[0]}, {st[1]}, {st[2]}, {st[3]}, {st[4]}, {st[5]}, Play)"


def e1_block(witness: list[int] | None, states: list[list] | None) -> str:
    """E1: the level is winnable from its start.

    The witness is the shortest winning action sequence found by enumerating the
    SHIPPED game, and every intermediate state below is the state that game is
    actually in at that point. The proof therefore checks, step by step, that the
    model tracks the implementation along the whole winning path: if they part
    company anywhere, this fails to verify.

    Written as non-recursive compositions of ten actions rather than as a fold
    over a sequence. Indexing a 45-element literal sequence was more than the
    prover would do, and the resulting failures said nothing about the model.
    """
    if not witness:
        return ("  // E1: no witness available (the level's graph has not been enumerated,\n"
                "  // or no win was reached within the caps); E1 is NOT claimed here.\n")
    if states is None:
        return ("  // E1: the shipped game could not be replayed to obtain the reference\n"
                "  // states, so E1 is NOT claimed here.\n")
    n = len(witness)
    bounds = list(range(0, n, CHUNK)) + [n]
    nchunks = len(bounds) - 1
    L = ["  // E1: winnable. WITNESS is the shortest winning action sequence found by",
         "  // enumerating the SHIPPED game; each intermediate state asserted below is",
         "  // that game's actual state after those actions, so the proof checks the",
         "  // model against the implementation at every step of the winning path.",
         "  // The last state is checked on status alone: the shipped game has loaded",
         "  // the next level by then, which this model does not cover.",
         f"  const WITNESS: seq<int> := [{', '.join(str(x) for x in witness)}]  // {n} actions",
         ""]
    for ci in range(nchunks):
        lo, hi = bounds[ci], bounds[ci + 1]
        expr = "s"
        for i in range(lo, hi):
            expr = f"Step({expr}, {witness[i]})"
        L.append(f"  function Chunk{ci}(s: S): S {{ {expr} }}")
    L.append("")
    all_expr = "s"
    for ci in range(nchunks):
        all_expr = f"Chunk{ci}({all_expr})"
    L.append(f"  function PlayWitness(s: S): S {{ {all_expr} }}")
    L.append("")
    for ci in range(nchunks):
        lo, hi = bounds[ci], bounds[ci + 1]
        last = (hi == n)
        L.append(f"  lemma E1_Chunk{ci}()")
        L.append(f"    ensures Chunk{ci}({_state_lit(states[lo])})"
                 + (".status == Win" if last else f" == {_state_lit(states[hi])}"))
        L.append("  {")
        L.append(f"    var s{lo} := {_state_lit(states[lo])};")
        for i in range(lo, hi):
            L.append(f"    var s{i + 1} := Step(s{i}, {witness[i]});")
            if i + 1 < n:
                L.append(f"    assert s{i + 1} == {_state_lit(states[i + 1])};"
                         f"  // the shipped game after {i + 1} action(s)")
        if last:
            L.append(f"    assert s{n}.status == Win;")
        L.append("  }")
        L.append("")
    L += ["  lemma E1_Winnable()",
          f"    ensures |WITNESS| == {n}",
          "    ensures PlayWitness(Start()).status == Win",
          "  {",
          f"    assert Start() == {_state_lit(states[0])};"]
    for ci in range(nchunks):
        L.append(f"    E1_Chunk{ci}();")
    L.append("  }")
    return "\n".join(L) + "\n"


def shipped_states(game: str, level: int, witness: list[int]) -> list[list] | None:
    """Replay the witness through the SHIPPED game and record (x, y, rot, lives,
    steps, eaten) after each action. Returns None if the game cannot be loaded."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from state_graph import abstract, make_game, register_module, set_energy_cells
        from arcengine import ActionInput, GameAction
    except Exception:
        return None
    spec = json.loads((ROOT / "artifacts" / "env" / game / f"level{level}.json").read_text())
    set_energy_cells(spec.get("energy"))
    try:
        _, g = make_game(game, level - 1)
    except SystemExit:
        return None
    register_module(g)
    def snap():
        a = abstract(g, level - 1)
        return [a["cx"], a["cy"], a["rot"], a["lives"], a["steps"], a["eaten"]]
    out = [snap()]
    for a in witness:
        g.perform_action(ActionInput(id=GameAction.from_id(a)), raw=True)
        out.append(snap())
    return out


TEMPLATE = r'''// GENERATED by scripts/gen_level_model.py from {json_rel}; do not edit.
// Rule-level model of ARC-AGI-3 public environment {game}, level {level}.
// Constants from the shipped level data; rules from reading the shipped source
// (see the generator's docstring). No escape constructs; see scripts/check_model.sh.
module {module} {{
  const W: int := {W}
  const H: int := {H}
  const START_X: int := {sx}
  const START_Y: int := {sy}
  const START_ROT: int := {srot}
  const GOAL_X: int := {gx}
  const GOAL_Y: int := {gy}
  const GOAL_ROT: int := {grot}
  const ROT_TILE_X: int := {rx}
  const ROT_TILE_Y: int := {ry}
  const STEPS: int := {steps}
  const DEC: int := {dec}
  const LIVES: int := {lives}
  const NE: int := {ne}          // energy pickups on this level
  const TILE_FLASH: bool := {tile_flash}  // cycling a tile into a match is free (level 1 only)

  // Wall cells, from the shipped level data (one disjunct per cell).
  predicate IsWall(x: int, y: int) {{
    {walls}
  }}

{energy_index}
{mask_ops}
  datatype Status = Play | Win | Over
  datatype S = S(x: int, y: int, rot: int, lives: int, steps: int, eaten: nat, status: Status)

  predicate Legal(s: S) {{
    0 <= s.x < W && 0 <= s.y < H && !IsWall(s.x, s.y) && 0 <= s.rot < 4
    && 1 <= s.lives <= LIVES && -DEC <= s.steps <= STEPS && EatenLegal(s.eaten)
  }}

  function Start(): S {{ S(START_X, START_Y, START_ROT, LIVES, STEPS, 0, Play) }}

  lemma StartLegal() ensures Legal(Start()) {{}}

  function Delta(a: int): (int, int)
  {{ if a == 1 then (0, -1) else if a == 2 then (0, 1) else if a == 3 then (-1, 0)
     else if a == 4 then (1, 0) else (0, 0) }}

  predicate Matches(rot: int) {{ rot == GOAL_ROT }}

  // One action on a Play state. Mirrors Ls20.step() at the rule level.
  // TOTAL in the action: an action outside the movement set leaves the state
  // untouched, which is what the shipped game does -- it completes the action
  // and returns before the step counter is touched.
  function Step(s: S, a: int): S
  {{
    if s.status != Play || a < 1 || a > 4 then s else
    var d := Delta(a);
    var tx := s.x + d.0;
    var ty := s.y + d.1;
    var isWall := IsWall(tx, ty);
    var isGoal := tx == GOAL_X && ty == GOAL_Y;
    var isRot := tx == ROT_TILE_X && ty == ROT_TILE_Y;
    var ei := EnergyIndex(tx, ty);
    var gotEnergy := !isWall && ei >= 0 && ei < NE && !HasBit(s.eaten, ei);
    var rot' := if !isWall && isRot then (s.rot + 1) % 4 else s.rot;
    // A flash consumes the action at no step cost: a goal reached with the wrong
    // rotation always flashes; a tile cycled into a match flashes on level 1 only.
    var flash := (!isWall && isGoal && !Matches(s.rot))
              || (TILE_FLASH && !isWall && isRot && Matches(rot'));
    var blocked := isWall || (isGoal && !Matches(s.rot));
    var x' := if blocked then s.x else tx;
    var y' := if blocked then s.y else ty;
    var eaten' := if gotEnergy then AddBit(s.eaten, ei) else s.eaten;
    if flash then S(x', y', rot', s.lives, s.steps, eaten', Play) else
    // An energy pickup refills the counter and skips this move's decrement.
    if gotEnergy then S(x', y', rot', s.lives, STEPS, eaten', Play) else
    var steps' := if s.steps >= 0 then s.steps - DEC else s.steps;
    var ranOut := steps' < 0;
    var won := x' == GOAL_X && y' == GOAL_Y && Matches(rot');
    if won then S(x', y', rot', s.lives, steps', eaten', Win) else
    if ranOut then (
      if s.lives - 1 == 0 then S(x', y', rot', 0, steps', eaten', Over)
      else S(START_X, START_Y, START_ROT, s.lives - 1, STEPS, 0, Play))
    else S(x', y', rot', s.lives, steps', eaten', Play)
  }}

  function Reset(s: S): S {{ Start() }}

  // Indexed rather than sliced: slicing a 45-element literal sequence put the
  // prover into work it could not finish, and an unfinished obligation is
  // unknown, not discharged.
  function RunFrom(s: S, path: seq<int>, i: nat): S
    requires i <= |path|
    decreases |path| - i
  {{ if i == |path| then s else RunFrom(Step(s, path[i]), path, i + 1) }}

  function Run(s: S, path: seq<int>): S {{ RunFrom(s, path, 0) }}

  // A non-movement action changes nothing (the shipped game returns before the
  // step counter is touched); this is what makes Step total.
  lemma NoOpAction(s: S, a: int)
    requires a < 1 || a > 4
    ensures Step(s, a) == s
  {{}}

  // E2: no action leaves the legal state space (an Over state is terminal and
  // carries lives = 0). The player is never on a wall cell and the border is
  // walled, so a legal position is interior and every neighbour is in range.
  predicate LegalOrOver(s: S) {{ Legal(s) || (s.status == Over && s.lives == 0) }}

  lemma E2_Closure(s: S, a: int)
    requires Legal(s)
    ensures LegalOrOver(Step(s, a))
  {{
    if 1 <= a <= 4 {{
      BorderFacts();
      assert 1 <= s.x <= W - 2 && 1 <= s.y <= H - 2;
    }}
    EatenBound(s, a);
  }}

  // The eaten bitmask stays legal: a pickup is consumed at most once, and the
  // mask space is enumerated explicitly (it has at most 2^NE elements, NE small),
  // so this is decided by case analysis rather than nonlinear arithmetic.
  lemma EatenBound(s: S, a: int)
    requires Legal(s)
    ensures EatenLegal(Step(s, a).eaten)
  {{
    if 1 <= a <= 4 {{
      var d := Delta(a);
      var ei := EnergyIndex(s.x + d.0, s.y + d.1);
      if 0 <= ei < NE && !HasBit(s.eaten, ei) {{
        EatenClosure(s.eaten, ei);
      }}
    }}
  }}

  lemma EatenClosure(m: nat, i: int)
    requires EatenLegal(m) && 0 <= i < NE && !HasBit(m, i)
    ensures EatenLegal(AddBit(m, i))
  {{}}

{border_facts}
  // E3: reset restores the start state (by definition in the model; the shipped
  // implementation is probed directly by scripts/state_graph.py).
  lemma E3_Reset(s: S) ensures Reset(s) == Start() {{}}

{e1_block}
  // Oracle entry points (compiled to JavaScript and called by the differential).
  function Apply(x: int, y: int, rot: int, lives: int, steps: int, eaten: nat, status: int, a: int): S
  {{ Step(S(x, y, rot, lives, steps, eaten, if status == 0 then Play else if status == 1 then Win else Over), a) }}
  function StatusCode(s: S): int {{ match s.status case Play => 0 case Win => 1 case Over => 2 }}
}}
'''


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="ls20")
    ap.add_argument("--level", type=int, default=1)
    a = ap.parse_args(argv)
    jp = ROOT / "artifacts" / "env" / a.game / f"level{a.level}.json"
    gp = ROOT / "artifacts" / "env" / a.game / f"graph_L{a.level}.json"
    d = json.loads(jp.read_text())
    guard(d, a.level)
    witness = None
    if gp.exists():
        g = json.loads(gp.read_text())
        witness = g.get("shortest_win_path")
    states = shipped_states(a.game, a.level, witness) if witness else None
    goal = d["goals"][0]
    module = f"{a.game.capitalize()}Level{a.level}"
    text = TEMPLATE.format(
        json_rel=jp.relative_to(ROOT), game=d["game"], level=a.level, module=module,
        W=len(d["cells_x"]), H=len(d["cells_y"]),
        sx=d["start"][0], sy=d["start"][1], srot=d["start_rotation_index"],
        gx=goal["cell"][0], gy=goal["cell"][1], grot=goal["rotation_index"],
        rx=d["rotation_tiles"][0][0], ry=d["rotation_tiles"][0][1],
        steps=d["step_counter"], dec=d["steps_decrement"], lives=d["lives"],
        ne=len(d["energy"]), tile_flash=str(bool(d["tile_flash"])).lower(),
        walls=wall_pred(d["walls"]), energy_index=energy_index(d["energy"]),
        mask_ops=mask_ops(len(d["energy"])),
        border_facts=border_facts(len(d["cells_x"]), len(d["cells_y"])),
        e1_block=e1_block(witness, states),
    )
    out = ROOT / "model" / f"{a.game}_level{a.level}.dfy"
    out.write_text(text)
    print(f"wrote {out} (module={module}, walls={len(d['walls'])}, energy={len(d['energy'])}, "
          f"dec={d['steps_decrement']}, tile_flash={d['tile_flash']}, witness_len={len(witness or [])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
