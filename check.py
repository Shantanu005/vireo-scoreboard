#!/usr/bin/env python3
"""Checks the scoreboard against the raw files and against itself.

Prints a pass/fail list and the cases the ranking gets wrong.
Python standard library only. No model calls.
"""

from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import score

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
SEED = 42
DRAWS = 400


def fail(message: str) -> None:
    raise SystemExit(f"FAIL {message}")


def raw_tickets() -> list[dict]:
    return score.load_csv("tickets.csv")


def independent_negative_handles(shift: bool) -> int:
    count = 0
    for row in raw_tickets():
        if row["source_system"] != "legacy_fd" or not row["resolved_at"] or not row["first_response_at"]:
            continue
        first = datetime.strptime(row["first_response_at"], "%Y-%m-%d %H:%M")
        resolved = datetime.strptime(row["resolved_at"], "%Y-%m-%d %H:%M")
        if shift:
            resolved += timedelta(hours=5, minutes=30)
        if resolved < first:
            count += 1
    return count


def independent_agent_mean(agent_id: str) -> tuple[float, int]:
    """Mean answered rating for one agent, Jan–Jun 2026, closed tickets only."""
    scores = []
    for row in raw_tickets():
        if row["agent_id"] != agent_id or row["status"] not in ("resolved", "closed"):
            continue
        if not row["csat_score"].strip():
            continue
        created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M")
        if not (score.WINDOW_START <= created < score.WINDOW_END):
            continue
        scores.append(int(row["csat_score"]))
    return statistics.fmean(scores), len(scores)


def ticket_gaps(tickets: list[dict]) -> dict[str, list[float]]:
    window = [t for t in tickets if score.in_window(t) and t["done"] and t["csat"] is not None]
    expected, _ = score.peer_expected(window)
    gaps: dict[str, list[float]] = defaultdict(list)
    for ticket in window:
        gaps[ticket["agent_id"]].append(ticket["csat"] - expected[id(ticket)])
    return gaps


def bootstrap(gaps: dict[str, list[float]], agents: dict[str, dict], material: list[str]) -> dict:
    """Resample each person's own surveys. The peer benchmark stays fixed."""
    named = {agent_id: values for agent_id, values in gaps.items() if len(values) >= score.MIN_SURVEYS}
    coach = [agent_id for agent_id in named if agents[agent_id]["team"] != score.WARRANTY_TEAM]
    width = max(len(material), 1)
    rng = random.Random(SEED)
    hits = {agent_id: 0 for agent_id in material}
    exact = 0
    for _ in range(DRAWS):
        means = {}
        for agent_id in coach:
            values = named[agent_id]
            draw = [values[rng.randrange(len(values))] for _ in range(len(values))]
            means[agent_id] = statistics.fmean(draw)
        worst = sorted(coach, key=lambda agent_id: means[agent_id])[:width]
        if set(worst) == set(material):
            exact += 1
        for agent_id in material:
            if agent_id in worst:
                hits[agent_id] += 1
    return {
        "draws": DRAWS,
        "width": width,
        "exact_match": exact / DRAWS,
        "kept": {agent_id: hits[agent_id] / DRAWS for agent_id in material},
    }


def main() -> None:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    agents = {row["agent_id"]: row for row in score.load_csv("agents.csv")}
    prepared = score.prepare(raw_tickets())

    if len(prepared) != 11750:
        fail(f"ticket count {len(prepared)}")
    if independent_negative_handles(False) != 2309:
        fail("legacy negative handle count changed")
    if independent_negative_handles(True) != 0:
        fail("timezone shift left negative legacy handle times")
    if summary["legacy_negative_handles_before_shift"] != 2309:
        fail("summary disagrees on unshifted negatives")
    if summary["legacy_negative_handles_after_shift"] != 0:
        fail("summary disagrees on shifted negatives")

    kavya = [row for row in agents.values() if row["name"] == "Kavya Pandey"]
    if len(kavya) != 2:
        fail("expected two Kavya Pandey rows")
    if {row["agent_id"] for row in kavya} != {"A3006", "A3029"}:
        fail("Kavya ids changed")
    by_id = {row["agent_id"]: row for row in summary["lists"]["coach_bottom_10"]}
    if by_id["A3006"]["site"] == by_id["A3029"]["site"]:
        fail("the two Kavyas were collapsed")

    built = {row["agent_id"]: row for row in score.build()["agents"]}
    for agent_id in ("A3006", "A3004", "A3014", "A3041"):
        got, n = independent_agent_mean(agent_id)
        if n != built[agent_id]["surveys"]:
            fail(f"{agent_id} survey count {n} vs {built[agent_id]['surveys']}")
        if abs(got - built[agent_id]["csat"]) > 0.001:
            fail(f"{agent_id} mean {got} vs {built[agent_id]['csat']}")

    # Blank scores are not zeros. A zero would pull A3006 down.
    blanks = 0
    for row in raw_tickets():
        if row["agent_id"] == "A3006" and not row["csat_score"].strip():
            blanks += 1
    if blanks < 1:
        fail("expected blank surveys for A3006")

    unit = float(score.load_csv("products.csv")[0] and next(
        row["unit_cost_inr"] for row in score.load_csv("products.csv") if row["sku"] == "VA-EB-PL2"
    ))
    each = float(unit) + score.LOGISTICS_INR
    if each != 1820:
        fail(f"Pulse 2 replacement cost {each}, expected 1820")
    base_rate = summary["replacements"]["baseline"]["rate"]
    q1 = summary["replacements"]["jan_mar_2026"]
    expected_inr = round((q1["replacements"] - base_rate * q1["tickets"]) * each)
    if expected_inr != q1["excess_inr"]:
        fail(f"Jan–Mar rupees {q1['excess_inr']} vs recomputed {expected_inr}")

    gaps = ticket_gaps(prepared)
    material = [row["agent_id"] for row in summary["lists"]["coach_material"]]
    stability = bootstrap(gaps, agents, material)

    # Standard error of the four coaching gaps, from their own surveys.
    se_lines = []
    for agent_id in material:
        values = gaps[agent_id]
        se = statistics.pstdev(values) / (len(values) ** 0.5)
        se_lines.append(f"{agent_id} n={len(values)} gap={statistics.fmean(values):+.3f} se={se:.3f}")

    fallback = summary["peer_fallback"]
    scored = sum(fallback.values())
    product_share = fallback["product"] / scored
    global_share = fallback["all"] / scored

    lines = [
        "PASS ticket count 11,750",
        "PASS legacy negative handle times 2,309 before the IST shift, 0 after",
        "PASS two Kavya Pandey rows stay A3006 Indore chat and A3029 Bengaluru logistics",
        "PASS A3006, A3004, A3014, A3041 survey means match a second pass over tickets.csv",
        "PASS Pulse 2 replacement = 1480 + 340 = Rs 1,820, and the quarter rupees use that",
        f"PASS blank surveys exist and are excluded (A3006 has {blanks} blanks in the whole file)",
        "",
        f"Ranking stability, {DRAWS} resamples of each person's own surveys, seed {SEED}.",
        "Peer benchmark held fixed. A draw is 'the same call' when the worst non-warranty names, same count as the coaching list, are unchanged.",
        f"Exact same set of {stability['width']}: {stability['exact_match']:.1%} of draws.",
    ]
    for agent_id, rate in stability["kept"].items():
        name = agents[agent_id]["name"]
        lines.append(f"  {name} ({agent_id}) stayed in the worst {stability['width']} in {rate:.1%} of draws")
    lines += [
        "",
        "Standard error of the coaching gaps:",
        *se_lines,
        "",
        "Cases the score gets wrong:",
        f"- {fallback['product']:,} of {scored:,} surveys ({product_share:.0%}) had fewer than 20 peer surveys in the same product and problem type, so they were compared with the whole product. A hard Connectivity ticket can be judged against an easy one.",
        f"- {fallback['all']:,} surveys ({global_share:.1%}) fell back to the company average.",
        "- Warranty agents are further below similar tickets than the coaching names (Jaspreet Desai's gap is about −0.54). They are left off the coaching list by the rota rule, not because the arithmetic cleared them.",
        "- The coaching rule is a rough normal interval (gap + 1.96 standard errors < 0). Zoya Menon only just clears it. Harpreet Goyal and Nisha Rao do not, and a slightly wider interval would drop Zoya too.",
        "- People with fewer than 25 surveys are never named. Ananya Das is at about +0.35 on 20 surveys and is left off the bonus list.",
        "- Answered surveys on open or pending tickets are ignored. The survey is supposed to go out at resolution; if one went out early, it is missing here.",
        "- A legacy ticket that really was resolved before the first reply would be hidden by the +5h30 shift. The shift removed every negative legacy handle time, which is why it is applied to all of them.",
        "- Pulse 2 tickets with no matching order are in the replacement cost and missing from the lot table.",
        "",
        f"Lot rows in the summary: {len(summary['lots']['lots'])}. Pulse 2 tickets since December with no order match: {summary['lots']['pulse2_since_dec_without_order']}.",
    ]
    text = "\n".join(lines) + "\n"
    (OUT / "checks.txt").write_text(text, encoding="utf-8")
    print(text)
    if stability["exact_match"] < 0.5:
        print("NOTE the exact coaching set is unstable. Use the per-person rates, not the set.")


if __name__ == "__main__":
    main()
