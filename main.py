"""
main.py — CLI entrypoint.

Usage:
    python main.py --orgs vercel,supabase,posthog --out results.csv

Requires env vars:
    GITHUB_TOKEN     (optional, raises rate limits from 60/hr to 5000/hr)
    ANTHROPIC_API_KEY (required, for outbound generation)
"""

import argparse
import csv
import os
import sys

from enrich import enrich_org
from outbound import generate_outbound
from discover import discover_orgs


def run(orgs: list[str], out_path: str, skip_outbound: bool = False):
    token = os.getenv("GITHUB_TOKEN")
    rows = []

    for org in orgs:
        org = org.strip()
        print(f"[enrich] {org} ...", file=sys.stderr)
        try:
            signal = enrich_org(org, token)

            if not signal.get("found"):
                print(f"  -> no public repos found, skipping", file=sys.stderr)
                continue

            print(f"  -> fit_score={signal['fit_score']}", file=sys.stderr)

            message = ""
            if not skip_outbound:
                print(f"  -> generating outbound...", file=sys.stderr)
                message = generate_outbound(signal)

            signal["outbound_message"] = message
            rows.append(signal)
        except Exception as e:
            print(f"  -> FAILED ({e}), skipping this org and continuing", file=sys.stderr)
            continue

    rows.sort(key=lambda r: r["fit_score"], reverse=True)

    if rows:
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nWrote {len(rows)} rows to {out_path}")
    else:
        print("No orgs enriched successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--orgs", help="comma-separated GitHub org names")
    parser.add_argument("--discover", action="store_true",
                         help="auto-discover candidate orgs instead of passing --orgs")
    parser.add_argument("--min-stars", type=int, default=2000)
    parser.add_argument("--language", default=None)
    parser.add_argument("--max-candidates", type=int, default=15)
    parser.add_argument("--out", default="results.csv")
    parser.add_argument("--skip-outbound", action="store_true",
                         help="only compute signals/fit score, skip Claude API calls")
    args = parser.parse_args()

    if args.discover:
        token = os.getenv("GITHUB_TOKEN")
        print(f"[discover] searching orgs with >{args.min_stars} stars...", file=sys.stderr)
        org_list = discover_orgs(
            min_stars=args.min_stars,
            language=args.language,
            max_results=args.max_candidates,
            token=token,
        )
        print(f"[discover] found {len(org_list)} candidate orgs: {org_list}", file=sys.stderr)
    elif args.orgs:
        org_list = args.orgs.split(",")
    else:
        parser.error("pass --orgs a,b,c or use --discover")

    run(org_list, args.out, args.skip_outbound)