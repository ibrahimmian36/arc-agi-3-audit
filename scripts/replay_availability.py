"""Where are the 342 ARC-AGI-3 human replays?

Every ARC-AGI-3 score is a ratio against a per-level human baseline. The ARC
Prize Foundation announced on 2026-04-14 that it had open-sourced the Public
Demo dataset, "which includes 342 human step-by-step replays" across the 25
public environments. Reference 2 of this audit cannot be checked against those
replays until they are located.

This script records, reproducibly, where we looked and what we found. It reads
only public listing APIs and the link printed in the announcement. It does not
authenticate, and it does not attempt to reach anything that is not openly
served: if the dataset is not public, that is the finding, not an obstacle.

Reject-only: "not located by these checks on this date" is not "does not exist".

Usage: replay_availability.py [--out artifacts/replays/availability.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A hit must mention ARC-AGI-3 AND human/replay data. Requiring only the second
# matched `arc-agi-benchmarking` (whose description says "baseline LLMs") and
# `arc_agi_2_human_testing` (which is ARC-AGI-2), and reported the dataset as
# located when it was not.
HUMAN_WORDS = ("human", "replay", "trajector", "playthrough")
AGI3_WORDS = ("agi-3", "agi_3", "agi3")
ANNOUNCEMENT = "https://arcprize.org/blog/arc-agi-3-human-dataset"
ANNOUNCED_LINK = "https://dub.link/vfwCqvb"   # the only link the announcement gives


def curl_json(url: str, timeout: int = 25):
    p = subprocess.run(["curl", "-s", "-m", str(timeout), "-A", "Mozilla/5.0", url],
                       capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def curl_status(url: str, timeout: int = 25) -> dict:
    p = subprocess.run(["curl", "-s", "-o", "/dev/null", "-A", "Mozilla/5.0",
                        "-w", "%{http_code} %{url_effective}", "-L", "--max-redirs", "8",
                        "-m", str(timeout), url], capture_output=True, text=True)
    parts = (p.stdout or "").split(" ", 1)
    return dict(status=parts[0] if parts else "", final_url=parts[1] if len(parts) > 1 else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "replays" / "availability.json")
    a = ap.parse_args(argv)
    a.out.parent.mkdir(parents=True, exist_ok=True)

    repos = curl_json("https://api.github.com/orgs/arcprize/repos?per_page=100&sort=updated") or []
    repo_rows = [dict(name=r["name"], license=(r.get("license") or {}).get("spdx_id"),
                      size_kb=r["size"], description=r.get("description"))
                 for r in repos if isinstance(r, dict) and "name" in r]
    def is_hit(text: str) -> bool:
        t = text.lower()
        return any(k in t for k in HUMAN_WORDS) and any(k in t for k in AGI3_WORDS)

    repo_hits = [r for r in repo_rows if is_hit(r["name"] + " " + (r["description"] or ""))]

    hf = curl_json("https://huggingface.co/api/datasets?author=arcprize&limit=100") or []
    hf_rows = [dict(id=d["id"], downloads=d.get("downloads")) for d in hf if isinstance(d, dict) and "id" in d]
    hf_hits = [d for d in hf_rows if is_hit(d["id"])]
    hf_agi3 = [d for d in hf_rows if any(k in d["id"].lower() for k in AGI3_WORDS)]

    link = curl_status(ANNOUNCED_LINK)

    out = dict(
        checked_on=str(date.today()), announcement=ANNOUNCEMENT, announced_link=ANNOUNCED_LINK,
        announced_link_result=link,
        github_org="arcprize", github_repo_count=len(repo_rows),
        github_repos=[r["name"] for r in repo_rows], github_keyword_hits=repo_hits,
        huggingface_author="arcprize", huggingface_datasets=[d["id"] for d in hf_rows],
        huggingface_keyword_hits=hf_hits, huggingface_agi3_datasets=hf_agi3,
        located=bool(repo_hits or hf_hits),
        note=("A hit requires both an ARC-AGI-3 reference and a human/replay reference. "
              "arc_agi_2_human_testing is ARC-AGI-2, and arc-agi-benchmarking's description "
              "mentions baseline LLMs, not human baselines."),
    )
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    log = (f"REPLAYS checked_on={out['checked_on']} github_repos={out['github_repo_count']} "
           f"github_keyword_hits={len(repo_hits)} huggingface_datasets={len(hf_rows)} "
           f"huggingface_agi3_datasets={len(hf_agi3)} huggingface_keyword_hits={len(hf_hits)} "
           f"announced_link_status={link['status']} "
           f"located={out['located']}\n"
           f"GITHUB {sorted(out['github_repos'])}\n"
           f"HUGGINGFACE {sorted(out['huggingface_datasets'])}\n")
    (a.out.parent / "availability.log").write_text(log)
    print(log.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
