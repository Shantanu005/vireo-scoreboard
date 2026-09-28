# Vireo scoreboard

A local scoreboard for Priya Raman: customer rating and time-to-finish per agent, for January–June 2026. It also prices the Pulse 2 replacement spike from the support policy.

No packages. No API key. No model call on a ticket.

## Run

Needs Python 3.9 or newer.

```bash
python3 score.py
python3 check.py
```

Then open `out/scoreboard.html`.

`score.py` reads `data/` and writes `out/summary.json`, `out/agents.csv`, and `out/scoreboard.html`.

`check.py` reruns the arithmetic a second way and writes `out/checks.txt`. It exits non-zero if a check fails.

## What the files are

| File | Used for |
| --- | --- |
| `data/tickets.csv` | Ratings, clocks, replacements |
| `data/agents.csv` | Name, site, team. Join on `agent_id` |
| `data/products.csv` | Pulse 2 unit cost |
| `data/orders.csv` | Lot codes, only for the lot table |
| `data/customers.csv` | Not used |

`memo-priya.md` is the one-page note. `submission-form.md` is the form.

## Decisions

1. **Window.** Named lists use tickets opened 1 Jan 2026 through 30 Jun 2026. That is the latest half-year in the file, after the rating slide. The trend and the replacement cost use the longer history.
2. **Blank ratings.** A blank survey is left out. It is not a zero. About 45% of customers do not answer. Policy section 8.
3. **Which tickets count.** Resolved and auto-closed only. Open and pending are left out of the averages. In this window, 101 answered surveys sit on open or pending tickets and are ignored.
4. **Clock.** Handle time is first human reply to resolution. Policy section 10. On `legacy_fd` rows the resolution time is UTC and the other timestamps are IST. The script adds 5 hours 30 minutes to those resolution times. Before the shift, 2,309 legacy tickets have a negative handle time. After it, none do.
5. **Names.** Two roster rows are both Kavya Pandey: A3006 (Indore, chat) and A3029 (Bengaluru, logistics). The script never joins on the display name.
6. **Minimum surveys.** A person needs 25 answered surveys in the window before they can be named for coaching or the bonus.
7. **Similar tickets.** Each survey is compared with other agents on the same product and the same problem type, when those peers have at least 20 surveys. Otherwise the comparison is the whole product. The person's own surveys are not in their own benchmark.
8. **Coaching flag.** Warranty (`Escalations & Warranty`) is left off the coaching list because that rota is given the angry hardware tickets on purpose. Among everyone else, a name is flagged only when a rough 95% interval for their gap sits entirely below zero (`gap + 1.96 * standard error < 0`).
9. **Bonus.** The five highest gaps among non-warranty agents with at least 25 surveys. Warranty was eligible. None of them landed in the five.
10. **Replacement rupees.** Policy section 5: unit cost plus Rs 340. Pulse 2 is Rs 1,480 + Rs 340 = Rs 1,820. Not Arjun's flat Rs 2,500. Baseline rate is Pulse 2 tickets from launch (15 Jul 2025) through 30 Sep 2025.
11. **No model in the run.** Arjun asked for something cheap at about 650 tickets a week. One run is Rs 0.

## If you are picking this up on Monday

1. Run the two commands above. Read `memo-priya.md` and `out/checks.txt` before you change a name.
2. There are two Kavya Pandeys. A3006 is the chat agent on the coaching list. A3029 is not.
3. Do not rank warranty against frontline on time-to-finish. Warranty takes days. Chat takes about 25 minutes. That is the job, not the person.
