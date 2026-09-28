# Submission form

## What did you build, and what business outcome does it move?

A local scoreboard (`python3 score.py`) of customer rating and time-to-finish per agent for January–June 2026, plus a fair comparison against coworkers on the same product and problem type. The note to Priya is `memo-priya.md`.

**Cut the share of answered surveys scored 1 or 2 from 28% (Jan–Jun 2026) back to 15% (before October 2025).** Other products are already at 16%. Pulse 2 earbuds are at 37%. Extra Pulse 2 replacements, at unit cost plus Rs 340 = Rs 1,820, were **Rs 10.1 lakh in Jan–Mar 2026** and **Rs 3.0 lakh in Apr–Jun 2026** (about Rs 14.3 lakh since December). Coaching the three people who clear the interval moves the company average by about **0.03 points**. It does not buy the 28% to 15% cut. The Rs 4 lakh should not be spent as a ten-person course.

## What does one run cost, and what would a month cost at Vireo's volume (roughly 650 tickets a week)?

No paid calls. The run is arithmetic in the standard library.

One run, any file size in this pack: **Rs 0**.

A month of volume: 650 tickets/week × 52 weeks / 12 = **2,817 tickets**. 2,817 × Rs 0 = **Rs 0**.

The assistant that wrote the code is Cursor. That is a subscription, not a per-ticket charge, and it is not part of a Vireo run.

## How do you know it works?

`python3 check.py` writes `out/checks.txt`.

Sample: 11,750 tickets. The named lists use 2,299 answered surveys on resolved or auto-closed tickets in Jan–Jun 2026. Coaching flags use 74, 67 and 88 surveys.

Checked, and they passed: ticket count; 2,309 negative legacy handle times before the +5h30 shift and 0 after; the two Kavya Pandey rows stay distinct; the survey means for A3006, A3004, A3014 and A3041 match a second pass over the CSV; Rs 1,820 × the excess replacements equals the published rupees.

Stability: 400 resamples of each person's own surveys, seed 42, peer benchmark held fixed. The exact set of three coaching names repeats in **17%** of draws. Kavya stays in the worst three in **73%**, Kapoor in **63%**, Zoya in **51%**. The averages are solid. The order of names near the cut is not.

The case it gets wrong: a survey whose product-and-problem cell has fewer than 20 peer surveys (882 of 2,299, 38%) is judged against the whole product, so a hard ticket can be compared with an easy one. Warranty agents are further below similar tickets than the coaching names and are left off by a rota rule, which may be the wrong call. Zoya only just clears the interval.

## Did you change, narrow, or push back on the client's ask?

Yes. Priya asked for one bottom ten. I still print that raw ten. I am not recommending they be the course.

Neha said the warranty rota is given the angriest customers on purpose. Six of the raw ten are that team. I took them off the coaching list on that instruction, on 28 Sep 2026, after the fair comparison still showed them low. The labels are too coarse to clear them, so the pushback is "read ten tickets before you spend", not "they are fine".

I also refused to rank teams against each other on handle time. Warranty takes days. Chat takes 25 minutes. Policy section 6 says tier 2 is measured in days.

The Rs 4 lakh is narrowed to two real conversations (Kavya A3006 and Kapoor), with Zoya as a maybe.

## What is wrong with what you are handing us?

- The exact coaching trio is unstable (17% of resamples). Selling Zoya as a firm third name would be overselling. Harpreet Goyal (gap −0.19) and Nisha Rao (−0.15) sit just outside the interval and would enter the list under a softer rule.
- 38% of surveys do not have a tight peer group, so the "similar tickets" number is sometimes the whole product.
- Warranty's larger gaps (Jaspreet Desai about −0.54) are excluded by rule. If the category tag really means the same work, they are the people furthest behind and I have pointed the budget away from them.
- 101 answered surveys on open or pending tickets in the window are dropped.
- The +5h30 shift is applied to every legacy resolution time. A ticket that truly closed before the first reply would be hidden. The shift clears all 2,309 negatives, which is why it is blanket.
- 1,232 Pulse 2 tickets since December have no matching order. They are in the rupee total and missing from the lot list. The lot rates are not a complete census.
- The 95% interval treats survey errors as normal and independent. They are not. It is a screen, not a test.
- Bonus order among Sukhwinder, Steven and Sai is close (gaps +0.39, +0.38, +0.34) and was not resampled. Bhavna and Kunal are the clear two.

## What did you deliberately leave out, and why that rather than something else?

I left out a per-ticket reading of the customer message and the agent note. Arjun ruled out a model call at this volume, and the rating Priya asked for does not need the text. I kept the fair-versus-raw split instead, because that split changes who gets the Rs 4 lakh.

I also left out repeat-contact cost, SLA-breach credits (Rs 350 a miss), and a full lot-quality tracker. The breach pool is real and smaller than the replacement spike. The lot table is a paragraph, not a second product. Building either would have come out of the check on whether the bottom ten is a queue.

`customers.csv` is unused. Care Plus and city do not change the coaching names at this cut.

## Anything you built or found that nobody asked for?

The Pulse 2 split. Other products did not slide. The replacement rupees at policy cost, and the October–December 2025 lots replacing at about 40% where an order was quoted. The timezone fix (without it, handle time on old tickets is negative). The second Kavya, kept separate. Six tickets that carry both a refund and a replacement, which policy section 5 says should not happen. They are counted in `summary.json` and not used in the ranking.

## What did you use AI for?

Cursor, model Grok 4.7, to read the pack, write `score.py` and `check.py`, and draft the memo. It helped on the joins, the UTC shift, and the first raw-versus-fair cut. It wasted a pass on a coaching list of four that the resample then broke, and an early search for `tickets.csv` before the file was in the folder. Thrown away: a per-ticket text model, merging the two Kavyas, Arjun's Rs 2,500, ranking on speed across teams, and the 0.15-point cut that kept Harpreet on the list.

No separate API bill. A Vireo run makes no paid calls.

Screen recording: not filmed from here. Walkthrough is `RECORDING.md`. Paste the Drive link over the next line.

Drive link:

## Someone picks this up on Monday and you are unreachable. The three things they need to know.

1. `python3 score.py` then `python3 check.py`. Read `memo-priya.md` and `out/checks.txt` before changing a name.
2. Two people are named Kavya Pandey. A3006 (Indore chat) is on the coaching list. A3029 (Bengaluru logistics) is not.
3. The 28% to 15% cut is a Pulse 2 replacement problem, about Rs 10.1 lakh in Jan–Mar 2026 at Rs 1,820 each. The coaching list moves the company rating by about 0.03 points.

## Honest hours spent.

2

## Github Repo Link

Not published. The folder `vireo-scoreboard` is the repo to upload. I did not push it, because a public URL needs your GitHub account.
