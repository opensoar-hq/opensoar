# Show HN Draft

## Research Summary

**Sources analyzed:** bestofshowhn.com (all-time + 2024-2025 rankings), Tracecat Show HN (264 pts, Apr 2024), CrowdSec HN post (170 pts, Oct 2020), Matano Launch HN (140 pts, Jan 2023), Myriade timing analysis (157K+ posts), HN official guidelines, multiple launch strategy blogs.

**Key findings:**

1. **Timing:** Post on **Sunday ~12:00 UTC (8:00 AM Eastern)**. Weekend posts have 20-30% higher breakout rates than weekdays. The "Tuesday 9 AM" conventional wisdom is wrong per data analysis of 157K+ Show HN posts. Sunday 0-2 UTC hits 15.7% breakout rate.

2. **Title formula:** The two highest-performing patterns are (a) naming the expensive incumbent you replace and (b) personal "I built" voice. Top examples: "Can't afford Bloomberg Terminal? I built the next best thing" (1,422 pts), "Memories -- Google Photos alternative" (797 pts).

3. **Body length:** Keep it short. 100-200 words in the post body. The current draft at ~400 words is 2x too long. Cut aggressively.

4. **What worked for Tracecat (264 pts):** Led with quantified pain ("100 alerts/day, 30 min each"), named Splunk SOAR ($100K+/yr), got organic OSS collaboration offers. Got grilled on security posture and integration depth.

5. **What kills posts:** Marketing language, generic titles, vote manipulation, not responding to comments in first 30-60 minutes, linking to landing page instead of repo.

6. **Competitive gap:** Shuffle SOAR has zero HN presence. The SOAR category on HN has only one real competitor post (Tracecat). The space is undercontested.

7. **TheHive angle:** TheHive was archived Dec 2025, community is actively seeking alternatives. TheHive 5 enters read-only mode without a StrangeBee license. This is a strong narrative hook.

8. **AI differentiator:** No competing SOAR Show HN post has led with AI. OpenSOAR's free built-in AI (Claude/OpenAI/Ollama) is genuinely unique positioning.

---

## Title (Option A — Recommended)

**Show HN: OpenSOAR -- Open-source SOAR platform, because Splunk SOAR costs $100K/yr**

## Title (Option B — Personal voice)

**Show HN: I built an open-source SOAR with AI playbooks after TheHive got archived**

## Title (Option C — Direct positioning)

**Show HN: OpenSOAR -- Open-source alternative to Splunk SOAR and Palo Alto XSOAR**

---

## Post Body

Link: https://github.com/opensoar-hq/opensoar-core

OpenSOAR is an open-source security automation (SOAR) platform. Playbooks are Python async functions — not YAML, not drag-and-drop. Apache 2.0, self-hosted, AI features included for free.

I built this after TheHive was archived in late 2025. The remaining options are Splunk SOAR / Palo Alto XSOAR ($100K+/yr with per-action billing), Tracecat (YAML-based), or Shuffle (GUI-first, no AI). I wanted something where a Python-literate analyst could automate triage in 20 lines of actual code.

What's different: playbooks use `@playbook` decorators with `asyncio.gather()` for parallel enrichment. AI triage, alert summarization, and playbook generation work with Claude, OpenAI, or Ollama — built into core, not a paid add-on. Ships with webhook ingestion, IOC extraction, case management, RBAC, and a dark-themed React UI.

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
```

Looking for feedback from SOC analysts and IR teams. What integrations matter most? Contributors welcome.

---

## TL;DR First Comment (post immediately after submission)

Creator here. Quick context on the decisions behind this:

**Why Python, not YAML/visual?** Security analysts who can code shouldn't have to fight a visual builder. Your playbooks are testable, lintable Python files. `pip install` anything you need.

**Why free AI?** Commercial SOARs charge extra for AI features. We think AI triage should be table stakes for any SOAR in 2026, not an upsell. Supports Claude, OpenAI, and Ollama (fully local).

**TheHive migration?** We wrote a migration guide: [link to docs/thehive-migration.md]. If you're running TheHive 4/5 and evaluating alternatives, happy to help.

**vs. Tracecat** — Tracecat uses YAML workflow definitions. OpenSOAR playbooks are pure Python. If you can write a FastAPI endpoint, you can write a playbook.

**vs. Shuffle** — Shuffle is GUI-first with 200+ integrations. We're code-first with fewer integrations today but a Python SDK to build your own.

**vs. n8n/Temporal** — Those are general-purpose. OpenSOAR has alert normalization, IOC extraction, severity triggers, and MITRE ATT&CK context built in.

Stack: Python 3.12, FastAPI, async SQLAlchemy, PostgreSQL, Redis, Celery, React 19, Vite.

Happy to go deep on architecture or deployment questions.

---

## Launch Checklist

- [ ] Post on **Sunday ~8:00 AM Eastern** (12:00 UTC)
- [ ] Link directly to GitHub repo, not a landing page
- [ ] Ensure README has screenshots/GIF demo and one-command Docker setup
- [ ] Spin up a read-only live demo instance with sample alerts if possible
- [ ] Block 2 hours after posting for comment responses — this is critical
- [ ] Do NOT share the HN link asking for upvotes (vote-ring detection will penalize)
- [ ] Have answers ready for: "what about security posture?", "how many integrations?", "why not just use Temporal?"
- [ ] Prepare a TheHive migration story for the comment thread
- [ ] Cross-post to r/netsec, r/selfhosted, r/cybersecurity 24-48 hours AFTER HN (not same day)
