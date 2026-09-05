"""ONE-TIME fetch of the PUBLIC environments (run once by hand; it downloads and
executes third-party game code and talks to the ARC API with HER key).

Requires ARC_API_KEY in the environment (refuses to run on the anonymous key,
which only unlocks 3 of 25 public games). Free: no model calls. Capped by
--max-games and --timeout. Writes artifacts/api/games.json (listing, without
wall-clock fields) and environment_files/<id>/<version>/.

Never touches semi-private or private environments: only what /api/games
returns for the key is listed, and only PUBLIC entries are downloaded.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from pathlib import Path

from arc_agi import Arcade, OperationMode

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-games", type=int, default=25)
    ap.add_argument("--timeout", type=int, default=600, help="wall cap in seconds")
    a = ap.parse_args(argv)
    key = os.environ.get("ARC_API_KEY", "")
    if not key:
        print("ARC_API_KEY is not set; refusing to use the anonymous key (3/25 games).", file=sys.stderr)
        return 2
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("wall cap reached")))
    signal.alarm(a.timeout)
    lg = logging.getLogger("fetch"); lg.setLevel(logging.INFO)
    arc = Arcade(arc_api_key=key, operation_mode=OperationMode.NORMAL, environments_dir=str(ROOT / "environment_files"),
                 recordings_dir=str(ROOT / "artifacts" / "recordings"), logger=lg)
    listing = []
    for e in arc.available_environments:
        d = json.loads(e.model_dump_json())
        d.pop("date_downloaded", None)
        # Designer-side fields the public docs do not advertise; not retained.
        d.pop("private_tags", None); d.pop("level_tags", None)
        listing.append(d)
    listing.sort(key=lambda d: d["game_id"])
    (ROOT / "artifacts" / "api").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts" / "api" / "games.json").write_text(json.dumps(listing, indent=1, sort_keys=True) + "\n")
    print(f"listed {len(listing)} games; baseline_actions present in listing for {sum(1 for d in listing if d.get('baseline_actions'))}")
    done = 0
    for d in listing[: a.max_games]:
        env = arc.make(d["game_id"], save_recording=False)
        print(f"  {d['game_id']}: {'ok' if env is not None else 'FAILED'}")
        done += env is not None
    print(f"fetched {done}/{min(len(listing), a.max_games)} into environment_files/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
