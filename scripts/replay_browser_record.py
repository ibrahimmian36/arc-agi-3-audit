"""Record what a real browser finds behind the announced replay link.

scripts/replay_availability.py checks the Foundation's public channels by
script. Its request to the announced link is refused by the link shortener
(HTTP 403, or 429 under repetition) whether or not it carries a browser
user-agent, because the shortener requires a real browser. On 2026-09-04 we
reported that refusal as the link "not resolving", and the dataset as not
locatable. That was an error of our instrument, found by two blind reviewers
who each said a 403 from a shortener is what a scripted request gets.

Opened in a real browser on 2026-09-05, the link resolves to a Google Drive
folder holding the dataset. This script records that observation, with its
provenance stated: it was observed by the authors in a browser, not fetched by
this script, and nothing from the folder is redistributed here.

Usage: replay_browser_record.py [--out artifacts/replays]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OBSERVATION = dict(
    observed_on="2026-09-05",
    method="opened in a real browser by the authors; not fetched by script",
    announced_link="https://dub.link/vfwCqvb",
    scripted_request_status="403 (429 under repetition), with or without a browser user-agent",
    resolves_to_host="drive.google.com",
    drive_folder_id="1FB7yae6VISRe2jDKPNZLJS0mAqIw9JZy",
    archive_drive_file_id="1aJmVxDPEyQ7m-FUVqHXCU_LcJGsnmBuk",
    folder_contents=[
        dict(name="arc_agi_3_public_demo_human_testing", kind="folder", modified="2026-04-15",
             children=["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52",
                       "lp85", "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48",
                       "sp80", "su15", "tn36", "tr87", "tu93", "vc33", "wa30"]),
        dict(name="arc_agi_3_public_demo_human_testing.zip", kind="archive", modified="2026-04-15",
             size="106 MB"),
        dict(name="testing_feedback_ratings.csv", kind="file", modified="2026-04-13", size="7 KB"),
    ],
    located=True,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "replays")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    o = OBSERVATION
    subs = o["folder_contents"][0]["children"]
    line = (f"BROWSER observed_on={o['observed_on']} located={o['located']} "
            f"resolves_to={o['resolves_to_host']} environment_folders={len(subs)} "
            f"archive={o['folder_contents'][1]['name']} archive_size={o['folder_contents'][1]['size'].replace(' ', '')} "
            f"scripted_status=refused method=browser\n")
    (a.out / "browser_observation.log").write_text(line)
    (a.out / "browser_observation.json").write_text(json.dumps(o, indent=1) + "\n")
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
