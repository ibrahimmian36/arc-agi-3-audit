// Model of the documented ARC-AGI-3 scoring rule (technical report v2
// arXiv:2603.24621v2 §4.1–4.3, docs.arcprize.org/methodology, 2026-09-03).
// Exact rational arithmetic. Two readings of the per-level cap are modelled
// because the report's Equation (1) and its prose disagree:
//   Prose: S = min(1.15, (h/a)^2)      (max 115%)
//   Eq:    S = (min(1.15, h/a))^2      (max 132.25%)
// Nothing here certifies the shipped scorer; the compiled form is an oracle
// that a differential runner compares against it.
module Scoring {
  const CAP: real := 1.15
  const CAPSQ: real := 1.3225

  function Ratio(h: nat, a: nat): real
    requires a > 0
  { (h as real) / (a as real) }

  function LevelScoreProse(h: nat, a: nat): real
    requires a > 0
  { var r := Ratio(h, a); var s := r * r; if s > CAP then CAP else s }

  function LevelScoreEq(h: nat, a: nat): real
    requires a > 0
  { var r := Ratio(h, a); var m := if r > CAP then CAP else r; m * m }

  // S1: the prose cap bounds the level score at 1.15.
  lemma S1_ProseCap(h: nat, a: nat)
    requires a > 0
    ensures 0.0 <= LevelScoreProse(h, a) <= CAP
  {
    var r := Ratio(h, a);
    assert r >= 0.0;
    assert r * r >= 0.0;
  }

  // S1': the equation cap bounds the level score at 1.3225.
  lemma S1_EqCap(h: nat, a: nat)
    requires a > 0
    ensures 0.0 <= LevelScoreEq(h, a) <= CAPSQ
  {
    var r := Ratio(h, a);
    var m := if r > CAP then CAP else r;
    assert LevelScoreEq(h, a) == m * m;
    assert 0.0 <= m <= CAP;
    MulMono(0.0, m, m);
    assert 0.0 <= m * m;
    calc <= {
      m * m;
      <= { MulMono(m, CAP, m); }
      CAP * m;
      == m * CAP;
      <= { MulMono(m, CAP, CAP); }
      CAP * CAP;
      == CAPSQ;
    }
  }

  // S2: matching the human baseline scores exactly 1 under both readings.
  lemma S2_Baseline(h: nat)
    requires h > 0
    ensures LevelScoreProse(h, h) == 1.0 && LevelScoreEq(h, h) == 1.0
  {
    DivSelf(h as real);
    assert Ratio(h, h) == 1.0;
  }

  lemma DivSelf(x: real)
    requires x > 0.0
    ensures x / x == 1.0
  {
    assert (x / x) * x == x;
    assert ((x / x) - 1.0) * x == 0.0;
    assert (x / x) - 1.0 == 0.0 by {
      if (x / x) - 1.0 != 0.0 {
        assert ((x / x) - 1.0) * x != 0.0;
      }
    }
  }

  // S3: more actions never score higher, under both readings.
  lemma S3_Monotone(h: nat, a1: nat, a2: nat)
    requires 0 < a1 <= a2
    ensures LevelScoreProse(h, a1) >= LevelScoreProse(h, a2)
    ensures LevelScoreEq(h, a1) >= LevelScoreEq(h, a2)
  {
    var r1 := Ratio(h, a1);
    var r2 := Ratio(h, a2);
    RatioMono(h, a1, a2);
    assert 0.0 <= r2 <= r1;
    MulMono(r2, r1, r2);
    MulMono(r2, r1, r1);
    assert r2 * r2 <= r1 * r1;
    var m1 := if r1 > CAP then CAP else r1;
    var m2 := if r2 > CAP then CAP else r2;
    assert 0.0 <= m2 <= m1;
    MulMono(m2, m1, m2);
    MulMono(m2, m1, m1);
    assert m2 * m2 <= m1 * m1;
  }

  lemma RatioMono(h: nat, a1: nat, a2: nat)
    requires 0 < a1 <= a2
    ensures Ratio(h, a1) >= Ratio(h, a2)
  {
    var hr := h as real;
    var x := a1 as real;
    var y := a2 as real;
    assert 0.0 < x <= y;
    assert hr >= 0.0;
    calc {
      hr / y;
    <= { DivMono(hr, x, y); }
      hr / x;
    }
  }

  lemma DivMono(hr: real, x: real, y: real)
    requires hr >= 0.0 && 0.0 < x <= y
    ensures hr / y <= hr / x
  {
    assert hr / y == hr * (1.0 / y);
    assert hr / x == hr * (1.0 / x);
    assert 1.0 / y <= 1.0 / x by {
      assert (1.0 / y) * y == 1.0;
      assert (1.0 / x) * x == 1.0;
      assert (1.0 / y) * x <= (1.0 / y) * y;
    }
    MulMono(1.0 / y, 1.0 / x, hr);
  }

  lemma MulMono(x: real, y: real, z: real)
    requires x <= y && z >= 0.0
    ensures x * z <= y * z
  {}

  // ---------------- Environment score ----------------

  // Weight of level l (1-indexed) is l; total weight of n levels is n(n+1)/2.
  function SumWeights(n: nat): nat
  { if n == 0 then 0 else n + SumWeights(n - 1) }

  // Weighted sum of the first i level scores, level l weighted by l.
  function Weighted(scores: seq<real>, i: nat): real
    requires i <= |scores|
  { if i == 0 then 0.0 else (i as real) * scores[i - 1] + Weighted(scores, i - 1) }

  // Levels are sequential: k completed levels means levels 1..k.
  predicate PrefixCompleted(completed: seq<bool>, k: nat)
    requires k <= |completed|
  { (forall i :: 0 <= i < k ==> completed[i]) && (forall i :: k <= i < |completed| ==> !completed[i]) }

  predicate ValidScores(scores: seq<real>, completed: seq<bool>)
    requires |scores| == |completed|
  { forall i :: 0 <= i < |scores| ==> scores[i] >= 0.0 && (!completed[i] ==> scores[i] == 0.0) }

  function CompletedShare(k: nat, n: nat): real
    requires 0 < n && k <= n
  { (SumWeights(k) as real) / (SumWeights(n) as real) }

  // D4: E = min( sum_{l<=k} w_l / W , sum_l w_l S_l / W ).
  function EnvScore(scores: seq<real>, completed: seq<bool>, k: nat): real
    requires |scores| == |completed| > 0
    requires k <= |scores|
    requires PrefixCompleted(completed, k)
    requires ValidScores(scores, completed)
  {
    var n := |scores|;
    var w := SumWeights(n) as real;
    var cap := CompletedShare(k, n);
    var raw := Weighted(scores, n) / w;
    if raw > cap then cap else raw
  }

  lemma SumWeightsPos(n: nat)
    requires n > 0
    ensures SumWeights(n) > 0
  {}

  lemma SumWeightsMono(k: nat, n: nat)
    requires k <= n
    ensures SumWeights(k) <= SumWeights(n)
  {}

  // S4: the environment score never exceeds the completed weighted share,
  // which never exceeds 1.
  lemma S4_Cap(scores: seq<real>, completed: seq<bool>, k: nat)
    requires |scores| == |completed| > 0
    requires k <= |scores|
    requires PrefixCompleted(completed, k)
    requires ValidScores(scores, completed)
    ensures EnvScore(scores, completed, k) <= CompletedShare(k, |scores|) <= 1.0
  {
    var n := |scores|;
    SumWeightsPos(n);
    SumWeightsMono(k, n);
    var w := SumWeights(n) as real;
    assert w > 0.0;
    assert (SumWeights(k) as real) <= w;
    assert CompletedShare(k, n) == (SumWeights(k) as real) / w;
    assert (SumWeights(k) as real) / w <= w / w == 1.0 by { DivMonoNum(SumWeights(k) as real, w, w); }
  }

  lemma DivMonoNum(p: real, q: real, w: real)
    requires w > 0.0 && p <= q
    ensures p / w <= q / w
  {
    assert p / w == p * (1.0 / w);
    assert q / w == q * (1.0 / w);
    assert 1.0 / w > 0.0;
    MulMono(p, q, 1.0 / w);
  }

  // S5: every level completed at exactly the baseline gives 1.
  lemma S5_AllAtBaseline(scores: seq<real>, completed: seq<bool>)
    requires |scores| == |completed| > 0
    requires forall i :: 0 <= i < |scores| ==> scores[i] == 1.0 && completed[i]
    ensures EnvScore(scores, completed, |scores|) == 1.0
  {
    var n := |scores|;
    SumWeightsPos(n);
    WeightedOnes(scores, n);
    assert Weighted(scores, n) == SumWeights(n) as real;
    assert CompletedShare(n, n) == 1.0;
  }

  lemma WeightedOnes(scores: seq<real>, i: nat)
    requires i <= |scores|
    requires forall j :: 0 <= j < |scores| ==> scores[j] == 1.0
    ensures Weighted(scores, i) == SumWeights(i) as real
  {}

  // S6: nothing completed scores 0.
  lemma S6_Nothing(scores: seq<real>, completed: seq<bool>)
    requires |scores| == |completed| > 0
    requires PrefixCompleted(completed, 0)
    requires ValidScores(scores, completed)
    ensures EnvScore(scores, completed, 0) == 0.0
  {
    var n := |scores|;
    SumWeightsPos(n);
    WeightedZeros(scores, n);
    assert CompletedShare(0, n) == 0.0;
  }

  lemma WeightedZeros(scores: seq<real>, i: nat)
    requires i <= |scores|
    requires forall j :: 0 <= j < |scores| ==> scores[j] == 0.0
    ensures Weighted(scores, i) == 0.0
  {}

  // ---------------- Entry points for the oracle ----------------

  // Per-level scores from baselines and actions; an uncompleted level scores 0.
  function LevelScores(baselines: seq<nat>, actions: seq<nat>, completed: seq<bool>, prose: bool): seq<real>
    requires |baselines| == |actions| == |completed|
    requires forall i :: 0 <= i < |actions| ==> (completed[i] ==> actions[i] > 0)
  {
    seq(|baselines|, i requires 0 <= i < |baselines| =>
      if !completed[i] then 0.0
      else if prose then LevelScoreProse(baselines[i], actions[i])
      else LevelScoreEq(baselines[i], actions[i]))
  }

  lemma LevelScoresValid(baselines: seq<nat>, actions: seq<nat>, completed: seq<bool>, prose: bool)
    requires |baselines| == |actions| == |completed|
    requires forall i :: 0 <= i < |actions| ==> (completed[i] ==> actions[i] > 0)
    ensures ValidScores(LevelScores(baselines, actions, completed, prose), completed)
  {
    var s := LevelScores(baselines, actions, completed, prose);
    forall i | 0 <= i < |s| ensures s[i] >= 0.0 && (!completed[i] ==> s[i] == 0.0) {
      if completed[i] {
        if prose { S1_ProseCap(baselines[i], actions[i]); } else { S1_EqCap(baselines[i], actions[i]); }
      }
    }
  }

  function CountPrefix(completed: seq<bool>): nat
    ensures CountPrefix(completed) <= |completed|
  { if |completed| == 0 || !completed[0] then 0 else 1 + CountPrefix(completed[1..]) }

  lemma CountPrefixIsPrefix(completed: seq<bool>)
    requires forall i :: 0 <= i < |completed| - 1 ==> (!completed[i] ==> !completed[i + 1])
    ensures PrefixCompleted(completed, CountPrefix(completed))
  {
    if |completed| == 0 || !completed[0] {
      forall i | 0 <= i < |completed| ensures !completed[i] { AllFalse(completed, i); }
    } else {
      var t := completed[1..];
      assert forall i :: 0 <= i < |t| ==> t[i] == completed[i + 1];
      CountPrefixIsPrefix(t);
    }
  }

  lemma AllFalse(c: seq<bool>, i: nat)
    requires |c| > 0 && !c[0] && i < |c|
    requires forall j :: 0 <= j < |c| - 1 ==> (!c[j] ==> !c[j + 1])
    ensures !c[i]
  {
    if i > 0 { AllFalse(c, i - 1); }
  }

  predicate Sequential(completed: seq<bool>)
  { forall i :: 0 <= i < |completed| - 1 ==> (!completed[i] ==> !completed[i + 1]) }

  // D6 read as a scoring rule: a level taking more than 5x its baseline is
  // not completed, and (levels being sequential) nothing after it is either.
  function ApplyCutoff(baselines: seq<nat>, actions: seq<nat>, completed: seq<bool>, mult: nat): seq<bool>
    requires |baselines| == |actions| == |completed|
    ensures |ApplyCutoff(baselines, actions, completed, mult)| == |completed|
    ensures Sequential(completed) ==> Sequential(ApplyCutoff(baselines, actions, completed, mult))
    ensures forall i :: 0 <= i < |completed| ==> (ApplyCutoff(baselines, actions, completed, mult)[i] ==> completed[i])
  {
    seq(|completed|, i requires 0 <= i < |completed| =>
      completed[i] && (forall j :: 0 <= j <= i ==> actions[j] <= mult * baselines[j]))
  }

  // Environment score (0..1) under the chosen reading. Returns the score as
  // an exact rational; the caller scales by 100.
  function EnvScoreFromActions(baselines: seq<nat>, actions: seq<nat>, completed: seq<bool>, prose: bool, cutoff: bool): real
    requires |baselines| == |actions| == |completed| > 0
    requires Sequential(completed)
    requires forall i :: 0 <= i < |actions| ==> (completed[i] ==> actions[i] > 0)
  {
    var c := if cutoff then ApplyCutoff(baselines, actions, completed, 5) else completed;
    var s := LevelScores(baselines, actions, c, prose);
    var k := CountPrefix(c);
    LevelScoresValid(baselines, actions, c, prose);
    CountPrefixIsPrefix(c);
    EnvScore(s, c, k)
  }

  function LevelScoresFromActions(baselines: seq<nat>, actions: seq<nat>, completed: seq<bool>, prose: bool, cutoff: bool): seq<real>
    requires |baselines| == |actions| == |completed| > 0
    requires forall i :: 0 <= i < |actions| ==> (completed[i] ==> actions[i] > 0)
  {
    var c := if cutoff then ApplyCutoff(baselines, actions, completed, 5) else completed;
    LevelScores(baselines, actions, c, prose)
  }
}
