Signal-Based Enrichment & Outbound Pipeline
Built for Aviator's GTM Engineer Intern application. This is a working version of what the JD describes: find companies with the engineering signals that matter (monorepo scale, PR throughput, CI adoption), then generate outbound that's personalized on real research, not a merge tag.
Why these signals
Aviator sells MergeQueue (merge conflict/broken build elimination) and FlexReview (review routing) into large, high-velocity engineering orgs. The ICP is:

Large monorepos → more merge contention
High PR throughput → more review bottleneck
Heavy GitHub Actions / CI usage → GitHub-native, easy integration
Multiple active repos → real engineering org, not a side project

All of this is public via the GitHub REST + Search API — no paid enrichment tool (Clay, Apollo) needed to prove the concept.
Pipeline

discover.py — auto-discovers candidate orgs via the GitHub Search API (star threshold, language, org-owned repos only) instead of relying on a hand-typed list. This is the "identify companies with the signals that matter" step done without Clay/Apollo.
enrich.py — pulls an org's repos, computes total monorepo size, CI adoption %, and 30-day PR throughput via the GitHub Search API. Outputs a 0-100 fit score. Auto-retries on dropped connections instead of failing the whole run over one flaky request.
outbound.py — feeds those signals into an LLM with a system prompt that hard-bans generic personalization and requires every claim in the email to be traceable to the signal data. Provider-agnostic by design — swap between Gemini and Claude with one env var, no code changes.
main.py — CLI that chains discover → enrich → outbound and ranks results by fit score into a CSV (drop-in ready for a CRM import). Skips and logs any org that fails instead of crashing the whole batch.
dashboard.py — Streamlit funnel view: ranked accounts, avg fit score, avg PR throughput, and an outbound-message preview per org. This is the "instrument the funnel" piece — see which plays are worth a sequencer slot before you spend send volume on them.

Usage
bashpip install -r requirements.txt
cp .env.example .env   # fill in GITHUB_TOKEN + your chosen LLM key
export $(cat .env | xargs)

# manual list
python main.py --orgs vercel,supabase,posthog,cal.com --out results.csv

# auto-discovery instead of a hand-typed list
python main.py --discover --min-stars 5000 --language typescript --max-candidates 15 --out results.csv

# dashboard
streamlit run dashboard.py
Output columns: org, repos_analyzed, biggest_repo, total_size_kb, ci_adoption_pct, pr_throughput_30d, languages, fit_score, outbound_message
results.csv in this repo is a real, unedited run against 10 auto-discovered orgs (>5,000 stars, TypeScript) — ranked top to bottom by fit score, with a generated email for each.
Which LLM provider to use
outbound.py supports either provider via one env var — no code changes:
LLM_PROVIDER=gemini   # or claude

gemini (default, used for the results.csv in this repo) — free, no card, get a key at aistudio.google.com/apikey. Good for iterating without spending anything.
claude — the JD explicitly lists "Claude API" as part of Aviator's stack. Swapping to it is a one-line env change; cost is a few cents for a full batch (Sonnet 5 pricing), and new Anthropic accounts get $5 in free trial credit.

Built it this way on purpose: a real GTM engineering pipeline shouldn't be locked to one model vendor, and swapping providers with zero code changes is the kind of thing that matters once this is running against a live CRM.
What I'd build first at Aviator (application answer)

I'd build the GitHub-signal enrichment layer first, before touching Clay or a sequencer. Aviator's ICP is entirely visible through public GitHub data — monorepo size, PR throughput, CI adoption are all queryable via the REST and Search APIs, no paid data source required to validate the model. I'd run this against a target list, rank by fit score, and only pass the top decile into AI-generated outbound that cites the actual repo and PR volume instead of a merge tag. That gets a scored, ranked, personalized target list into the CRM in one pipeline run, and the fit-score weights become a feedback loop once reply/meeting data comes back from the sequencer — the system gets smarter about what "good fit" actually means instead of staying static.

Notes / next steps

Rate limits: unauthenticated GitHub calls are capped at 60/hr — a GITHUB_TOKEN bumps that to 5,000/hr.
--skip-outbound runs signal scoring only, useful for testing without burning any LLM API calls.
Next: pipe results.csv straight into a HubSpot/Instantly import via their REST APIs, and add a hiring-signal check (careers page / job board scan for "DevEx", "platform engineer") to catch the "recent DevEx or platform hires" signal from the JD that pure GitHub data can't see.
