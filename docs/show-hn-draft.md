# Show HN Draft

## Research Summary

**Sources analyzed:** bestofshowhn.com (all-time + 2024-2025 rankings), Tracecat Show HN (264 pts, Apr 2024), CrowdSec HN post (170 pts, Oct 2020), Matano Launch HN (140 pts, Jan 2023), Myriade timing analysis (157K+ posts), HN official guidelines, multiple launch strategy blogs, OPE-22 landscape research (10 projects analyzed), OPE-23 TheHive user migration research.

**Key findings:**

1. **Timing:** Post on **Sunday ~12:00 UTC (8:00 AM Eastern)**. Weekend posts have 20-30% higher breakout rates than weekdays. Sunday 0-2 UTC hits 15.7% breakout rate.

2. **Title formula:** The two highest-performing patterns are (a) naming the expensive incumbent you replace and (b) personal "I built" voice. Top examples: "Can't afford Bloomberg Terminal? I built the next best thing" (1,422 pts).

3. **Body length:** Keep it short. 100-200 words in the post body.

4. **What worked for Tracecat (264 pts):** Led with quantified pain ("100 alerts/day, 30 min each"), named Splunk SOAR ($100K+/yr), got organic OSS collaboration offers.

5. **What kills posts:** Marketing language, generic titles, vote manipulation, not responding to comments in first 30-60 minutes, linking to landing page instead of repo.

6. **Competitive gap:** Shuffle SOAR has zero HN presence. The SOAR category on HN has only one real competitor post (Tracecat). The space is undercontested.

7. **TheHive angle (STRONG):** TheHive archived Dec 2025, ~3,900 stars. Users fragmented across Shuffle (no case management), DFIR-IRIS (case-only, no automation), and Tracecat (still beta after 2 years, switched Apache→AGPL). No single successor. This is the narrative hook.

8. **License bait-and-switch fatigue:** TheHive went AGPL→closed. Tracecat went Apache→AGPL. Shuffle is AGPLv3. Users are burned. Apache 2.0 forever is a real differentiator.

9. **AI differentiator:** No competing SOAR Show HN post has led with AI. OpenSOAR's free built-in AI (Claude/OpenAI/Ollama) is genuinely unique positioning.

---

## Title (Recommended)

**Show HN: OpenSOAR – TheHive died, Splunk SOAR costs $100K/yr, so I built an open-source SOAR**

## Title (Option B — Problem-first)

**Show HN: OpenSOAR – Open-source SOAR for the 3,900 teams that lost TheHive**

## Title (Option C — Direct technical)

**Show HN: OpenSOAR – Python-native SOAR with free AI, because YAML playbooks are a dead end**

---

## Post Body

Link: https://github.com/opensoar-hq/opensoar-core

TheHive was the open-source IR platform for 3,900+ teams. StrangeBee archived it in December 2025 and locked TheHive 5 behind a commercial license. The remaining options: Splunk SOAR / Palo Alto XSOAR ($100K+/yr with per-action billing), Shuffle (no case management), Tracecat (still beta, switched from Apache to AGPL), or DFIR-IRIS (case management only, no automation).

I built OpenSOAR to fill that gap. Playbooks are Python async functions with `@playbook` decorators — not YAML, not drag-and-drop. AI triage, alert summarization, and playbook generation work with Claude, OpenAI, or Ollama — built into core, free forever. Apache 2.0, no license bait-and-switch.

```bash
git clone https://github.com/opensoar-hq/opensoar-core.git && cd opensoar-core
docker compose up -d
# API at :8000, UI at :3000
```

TheHive migration guide: [docs/migrating-from-thehive.md](https://github.com/opensoar-hq/opensoar-core/blob/main/docs/migrating-from-thehive.md)

Looking for feedback from SOC analysts and IR teams. What integrations matter most?

---

## First Comment (post immediately after submission)

Creator here. I know this space well — I researched every open-source SOAR attempt before building this. Quick context on why I made specific choices:

**Why Python, not YAML/visual?** Every SOAR that went YAML-first (StackStorm, Shuffle) created a second language security analysts have to learn. Your playbooks should be testable, lintable Python files. `pip install` anything you need. If you can write a FastAPI endpoint, you can write a playbook.

**Why is AI free?** Commercial SOARs charge extra for AI features. Tracecat has AI but it's behind their cloud tier. We think AI triage should be table stakes in 2026. Supports Claude, OpenAI, and Ollama (fully local, no data leaves your network).

**Why Apache 2.0?** TheHive started AGPL, then went fully closed-source. Tracecat started Apache 2.0, then switched to AGPL. Shuffle is AGPLv3. Users are rightfully burned by license bait-and-switch. Our license is Apache 2.0 and stays Apache 2.0. Period.

**vs. Shuffle SOAR** (~2,200 stars) — Shuffle is GUI-first with auto-generated integrations from OpenAPI specs. Great for visual workflows, but no case management and no AI. We're code-first with deeper integrations and AI built in.

**vs. Tracecat** (~3,500 stars, YC W24) — Closest to us architecturally (Python/FastAPI/Temporal). But still in beta after 2 years, two-person team, switched to AGPL-3.0. We ship stable releases under Apache 2.0.

**vs. DFIR-IRIS** — DFIR-IRIS is excellent for digital forensics case management. But it's not a SOAR — no playbook automation, no alert normalization, no AI. We see DFIR-IRIS as complementary. Use DFIR-IRIS for forensic cases, OpenSOAR for automated triage and response.

**vs. n8n/Temporal** — General-purpose automation tools. OpenSOAR has alert normalization, IOC extraction, severity triggers, MITRE ATT&CK context, and RBAC built in. Security-specific primitives matter.

**TheHive migration?** We wrote a full guide mapping TheHive concepts to OpenSOAR: alerts, cases, observables, Cortex analyzers → integration adapters. If you're evaluating alternatives, happy to help in the thread.

Stack: Python 3.12, FastAPI, async SQLAlchemy, PostgreSQL, Redis, Celery, React 19, Vite. 168+ tests, Docker multi-target builds.

---

## Launch Checklist

- [ ] Post on **Sunday ~8:00 AM Eastern** (12:00 UTC)
- [ ] Link directly to GitHub repo, not a landing page
- [ ] Ensure README has screenshots/GIF demo and one-command Docker setup
- [ ] Spin up a read-only live demo instance with sample alerts if possible
- [ ] Block 2 hours after posting for comment responses — this is critical
- [ ] Do NOT share the HN link asking for upvotes (vote-ring detection will penalize)
- [ ] Have answers ready for: "what about security posture?", "how many integrations?", "why not just use Temporal?"
- [ ] Prepare TheHive migration story with specific feature mapping for the comment thread
- [ ] Cross-post to r/netsec, r/selfhosted, r/cybersecurity 24-48 hours AFTER HN (not same day)
- [ ] Post in TheHive Discord 24h after HN launch (when stars give credibility)
- [ ] Engage DFIR-IRIS GitHub Discussions — position as complementary
