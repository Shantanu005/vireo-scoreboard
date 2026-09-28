#!/usr/bin/env python3
"""Vireo scoreboard.

Ranks support agents for Priya Raman's Q3 coaching budget.

Decisions are written down in README.md. This file only does the arithmetic.
No network calls. No model calls. Python standard library only.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "out"

# Policy v3.2 section 5: replacement = unit cost + Rs 340 logistics.
LOGISTICS_INR = 340
# Named lists need this many answered surveys in the decision window.
MIN_SURVEYS = 25
# Peer average needs this many other agents' surveys, else fall back.
MIN_PEERS = 20
WINDOW_START = datetime(2026, 1, 1)
WINDOW_END = datetime(2026, 7, 1)
PL2_SKU = "VA-EB-PL2"
WARRANTY_TEAM = "Escalations & Warranty"
# Jul 15 2025 is the Pulse 2 launch in products.csv. Baseline is launch
# through September, before the festive packs.
PL2_BASE_START = datetime(2025, 7, 15)
PL2_BASE_END = datetime(2025, 10, 1)
SINCE_DEC = datetime(2025, 12, 1)


def parse_ts(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def load_csv(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def fmt_duration(hours: float | None) -> str:
    if hours is None:
        return ""
    if hours < 12:
        return f"{round(hours * 60)} min"
    return f"{hours / 24:.1f} days"


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.fmean(values)


def prepare(tickets: list[dict]) -> list[dict]:
    """Attach clocks. Legacy resolution timestamps are UTC; shift them to IST."""
    prepared = []
    for row in tickets:
        created = parse_ts(row["created_at"])
        first = parse_ts(row["first_response_at"])
        resolved = parse_ts(row["resolved_at"])
        if resolved is not None and row["source_system"] == "legacy_fd":
            resolved = resolved + timedelta(hours=5, minutes=30)
        handle = None
        if first is not None and resolved is not None:
            handle = (resolved - first).total_seconds() / 3600
        csat = int(row["csat_score"]) if row["csat_score"].strip() else None
        prepared.append(
            {
                **row,
                "created": created,
                "first": first,
                "resolved": resolved,
                "handle_h": handle,
                "csat": csat,
                "done": row["status"] in ("resolved", "closed"),
                "replacement": row["replacement_issued"].strip().upper() == "Y",
            }
        )
    return prepared


def in_window(ticket: dict) -> bool:
    created = ticket["created"]
    return created is not None and WINDOW_START <= created < WINDOW_END


def peer_expected(scored: list[dict]) -> dict[str, float]:
    """Expected rating for each ticket: other agents, same product and problem.

    Falls back to the product, then to all other agents, when the peer
    group has fewer than MIN_PEERS surveys. The agent's own surveys are
    not part of their expected rating.
    """
    by_cell: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    by_sku: dict[str, list[tuple[str, int]]] = defaultdict(list)
    everyone: list[tuple[str, int]] = []
    for ticket in scored:
        item = (ticket["agent_id"], ticket["csat"])
        by_cell[(ticket["product_sku"], ticket["category"])].append(item)
        by_sku[ticket["product_sku"]].append(item)
        everyone.append(item)

    expected: dict[str, float] = {}
    fallback = {"cell": 0, "product": 0, "all": 0}
    for ticket in scored:
        agent = ticket["agent_id"]
        cell = (ticket["product_sku"], ticket["category"])
        peers = [score for other, score in by_cell[cell] if other != agent]
        level = "cell"
        if len(peers) < MIN_PEERS:
            peers = [score for other, score in by_sku[ticket["product_sku"]] if other != agent]
            level = "product"
        if len(peers) < MIN_PEERS:
            peers = [score for other, score in everyone if other != agent]
            level = "all"
        fallback[level] += 1
        expected[id(ticket)] = statistics.fmean(peers)
        ticket["_peer_level"] = level
    ticket_fallback_counts = fallback
    return expected, ticket_fallback_counts


def agent_rows(tickets: list[dict], agents: dict[str, dict]) -> list[dict]:
    window = [t for t in tickets if in_window(t)]
    scored = [t for t in window if t["done"] and t["csat"] is not None]
    expected, fallback_counts = peer_expected(scored)
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for ticket in window:
        by_agent[ticket["agent_id"]].append(ticket)

    rows = []
    for agent_id, own in by_agent.items():
        profile = agents[agent_id]
        surveys = [t for t in own if t["done"] and t["csat"] is not None]
        handles = [t["handle_h"] for t in own if t["done"] and t["handle_h"] is not None and t["handle_h"] >= 0]
        scores = [t["csat"] for t in surveys]
        gaps = [t["csat"] - expected[id(t)] for t in surveys]
        gap_se = None
        if len(gaps) >= 2:
            gap_se = statistics.pstdev(gaps) / (len(gaps) ** 0.5)
        pl2 = sum(1 for t in own if t["product_sku"] == PL2_SKU)
        detractors = sum(1 for score in scores if score <= 2)
        rows.append(
            {
                "agent_id": agent_id,
                "name": profile["name"],
                "site": profile["site"],
                "team": profile["team"],
                "shift": profile["shift"],
                "tier": int(profile["tier"]),
                "warranty_team": profile["team"] == WARRANTY_TEAM,
                "tickets": len(own),
                "surveys": len(surveys),
                "csat": round(statistics.fmean(scores), 3) if scores else None,
                "detractor_rate": round(detractors / len(scores), 3) if scores else None,
                "gap": round(statistics.fmean(gaps), 3) if gaps else None,
                "gap_se": round(gap_se, 3) if gap_se is not None else None,
                "expected": round(statistics.fmean(scores) - statistics.fmean(gaps), 3) if gaps else None,
                "handle_median_h": round(statistics.median(handles), 2) if handles else None,
                "handle_label": fmt_duration(statistics.median(handles) if handles else None),
                "pl2_share": round(pl2 / len(own), 3) if own else None,
                "named": len(surveys) >= MIN_SURVEYS,
            }
        )
    rows.sort(key=lambda row: (row["csat"] is None, row["csat"] if row["csat"] is not None else 99))
    return rows, fallback_counts, len(scored)


def replacement_story(tickets: list[dict], products: dict[str, dict]) -> dict:
    unit = float(products[PL2_SKU]["unit_cost_inr"])
    each = unit + LOGISTICS_INR
    pl2 = [t for t in tickets if t["product_sku"] == PL2_SKU and t["created"] is not None]

    def block(start: datetime, end: datetime) -> dict:
        chosen = [t for t in pl2 if start <= t["created"] < end]
        repl = sum(1 for t in chosen if t["replacement"])
        return {"tickets": len(chosen), "replacements": repl, "rate": (repl / len(chosen)) if chosen else None}

    base = block(PL2_BASE_START, PL2_BASE_END)
    since = block(SINCE_DEC, WINDOW_END)
    q1 = block(datetime(2026, 1, 1), datetime(2026, 4, 1))
    q2 = block(datetime(2026, 4, 1), datetime(2026, 7, 1))
    excess_since = since["replacements"] - base["rate"] * since["tickets"]
    excess_q1 = q1["replacements"] - base["rate"] * q1["tickets"]
    excess_q2 = q2["replacements"] - base["rate"] * q2["tickets"]
    return {
        "unit_cost_inr": unit,
        "logistics_inr": LOGISTICS_INR,
        "each_inr": each,
        "baseline": {**base, "label": "15 Jul–30 Sep 2025"},
        "since_december": {
            **since,
            "label": "1 Dec 2025–30 Jun 2026",
            "excess_replacements": round(excess_since, 1),
            "excess_inr": round(excess_since * each),
        },
        "jan_mar_2026": {
            **q1,
            "label": "Jan–Mar 2026",
            "excess_replacements": round(excess_q1, 1),
            "excess_inr": round(excess_q1 * each),
        },
        "apr_jun_2026": {
            **q2,
            "label": "Apr–Jun 2026",
            "excess_replacements": round(excess_q2, 1),
            "excess_inr": round(excess_q2 * each),
        },
    }


def detractor_story(tickets: list[dict]) -> dict:
    def rate(chosen: list[dict]) -> dict:
        scores = [t["csat"] for t in chosen if t["done"] and t["csat"] is not None]
        bad = sum(1 for score in scores if score <= 2)
        return {"surveys": len(scores), "detractors": bad, "rate": bad / len(scores) if scores else None}

    early = [t for t in tickets if t["created"] and t["created"] < datetime(2025, 10, 1)]
    window = [t for t in tickets if in_window(t)]
    window_pl2 = [t for t in window if t["product_sku"] == PL2_SKU]
    window_other = [t for t in window if t["product_sku"] != PL2_SKU]
    return {
        "jan_sep_2025": rate(early),
        "jan_jun_2026": rate(window),
        "jan_jun_2026_pulse2": rate(window_pl2),
        "jan_jun_2026_other": rate(window_other),
    }


def company_csat(tickets: list[dict]) -> dict:
    def avg(chosen: list[dict]) -> dict:
        scores = [t["csat"] for t in chosen if t["done"] and t["csat"] is not None]
        return {"surveys": len(scores), "csat": round(statistics.fmean(scores), 3) if scores else None}

    early = [t for t in tickets if t["created"] and t["created"] < datetime(2025, 10, 1)]
    window = [t for t in tickets if in_window(t)]
    months = []
    cursor = datetime(2025, 7, 1)
    while cursor < WINDOW_END:
        nxt = datetime(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        chosen = [t for t in tickets if t["created"] and cursor <= t["created"] < nxt]
        pl2 = [t for t in chosen if t["product_sku"] == PL2_SKU]
        other = [t for t in chosen if t["product_sku"] != PL2_SKU]
        months.append(
            {
                "month": cursor.strftime("%Y-%m"),
                "all": avg(chosen),
                "pulse2": avg(pl2),
                "other": avg(other),
            }
        )
        cursor = nxt
    return {"before_oct_2025": avg(early), "jan_jun_2026": avg(window), "months": months}


def lot_story(tickets: list[dict], orders: dict[str, dict]) -> list[dict]:
    """Pulse 2 replacement rate by manufacturing lot, since December 2025.

    Only tickets with an order id that exists in orders.csv. Tickets with no
    quoted order are counted in the cost figure and left out of this table.
    """
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    missing_order = 0
    for ticket in tickets:
        if ticket["product_sku"] != PL2_SKU or ticket["created"] is None:
            continue
        if ticket["created"] < SINCE_DEC:
            continue
        if not ticket["replacement"]:
            # still count the ticket in the denominator when we know the lot
            pass
        order = orders.get(ticket["order_id"])
        if order is None:
            missing_order += 1
            continue
        lot = order["lot_code"] or "UNKNOWN"
        counts[lot][0] += 1
        if ticket["replacement"]:
            counts[lot][1] += 1
    rows = []
    for lot, (tickets_n, repl) in counts.items():
        rows.append(
            {
                "lot_code": lot,
                "tickets": tickets_n,
                "replacements": repl,
                "rate": round(repl / tickets_n, 3) if tickets_n else None,
            }
        )
    solid = [row for row in rows if row["tickets"] >= 40]
    solid.sort(key=lambda row: (-(row["rate"] or 0), -row["replacements"]))
    return {"lots": solid[:8], "pulse2_since_dec_without_order": missing_order}


def both_refund_and_replacement(tickets: list[dict]) -> int:
    return sum(1 for t in tickets if t["replacement"] and t["refund_amount_inr"].strip())


def negative_handles(tickets: list[dict], shift_legacy: bool) -> int:
    count = 0
    for ticket in tickets:
        if ticket["source_system"] != "legacy_fd":
            continue
        first = parse_ts(ticket["first_response_at"])
        resolved = parse_ts(ticket["resolved_at"])
        if first is None or resolved is None:
            continue
        if shift_legacy:
            resolved = resolved + timedelta(hours=5, minutes=30)
        if resolved < first:
            count += 1
    return count


def select_lists(rows: list[dict]) -> dict:
    named = [row for row in rows if row["named"] and row["csat"] is not None and row["gap"] is not None]
    raw = sorted(named, key=lambda row: (row["csat"], -row["surveys"]))
    fair = sorted(named, key=lambda row: (row["gap"], -row["surveys"]))
    coach_pool = [row for row in fair if not row["warranty_team"]]
    # Material: a rough 95% interval for the gap sits entirely below zero.
    # Names that only just clear it are still fragile. See check.py.
    material = [
        row
        for row in coach_pool
        if row["gap"] is not None
        and row["gap_se"] is not None
        and row["gap"] + 1.96 * row["gap_se"] < 0
    ]
    return {
        "raw_bottom_10": raw[:10],
        "fair_bottom_including_warranty": fair[:10],
        "coach_bottom_10": coach_pool[:10],
        "coach_material": material,
        "bonus_top_5": list(reversed(coach_pool[-5:])),
    }


def coaching_lift(rows: list[dict], lists: dict, scored_n: int) -> dict:
    """How far company CSAT moves if the material names merely match peers."""
    points = 0.0
    surveys = 0
    for row in lists["coach_material"]:
        points += (-row["gap"]) * row["surveys"]
        surveys += row["surveys"]
    return {
        "people": len(lists["coach_material"]),
        "surveys": surveys,
        "company_surveys": scored_n,
        "mean_lift": round(points / scored_n, 3) if scored_n else None,
    }


def team_handle(tickets: list[dict], agents: dict[str, dict]) -> list[dict]:
    by_team: dict[str, list[float]] = defaultdict(list)
    for ticket in tickets:
        if not in_window(ticket) or not ticket["done"]:
            continue
        if ticket["handle_h"] is None or ticket["handle_h"] < 0:
            continue
        by_team[agents[ticket["agent_id"]]["team"]].append(ticket["handle_h"])
    rows = []
    for team, hours in sorted(by_team.items(), key=lambda item: statistics.median(item[1])):
        rows.append(
            {
                "team": team,
                "closed": len(hours),
                "median_h": round(statistics.median(hours), 2),
                "label": fmt_duration(statistics.median(hours)),
            }
        )
    return rows


def write_agents_csv(rows: list[dict]) -> None:
    fields = [
        "agent_id",
        "name",
        "site",
        "team",
        "shift",
        "surveys",
        "csat",
        "expected",
        "gap",
        "handle_label",
        "detractor_rate",
        "pl2_share",
        "warranty_team",
        "named",
    ]
    with (OUT / "agents.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: (item["gap"] is None, item["gap"] or 0)):
            writer.writerow(row)


def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def person(row: dict) -> str:
    return f"{row['name']} ({row['agent_id']}), {row['site']}"


def table(headers: list[str], records: list[list[object]]) -> str:
    head = "".join(f"<th>{html_escape(header)}</th>" for header in headers)
    body = []
    for record in records:
        cells = "".join(f"<td>{html_escape(cell)}</td>" for cell in record)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(summary: dict) -> None:
    lists = summary["lists"]
    repl = summary["replacements"]
    det = summary["detractors"]
    csat = summary["csat"]
    lift = summary["coaching_lift"]
    raw_rows = [
        [person(row), "Warranty" if row["warranty_team"] else row["team"].split()[0], f"{row['csat']:.2f}", row["surveys"], row["handle_label"]]
        for row in lists["raw_bottom_10"]
    ]
    coach_rows = [
        [
            person(row),
            row["team"].replace(" Frontline", "").replace("Escalations & Warranty", "Warranty"),
            f"{row['csat']:.2f}",
            f"{row['expected']:.2f}",
            f"{row['gap']:+.2f}",
            row["surveys"],
            row["handle_label"],
        ]
        for row in lists["coach_bottom_10"]
    ]
    bonus_rows = [
        [person(row), row["team"].replace(" Frontline", ""), f"{row['csat']:.2f}", f"{row['expected']:.2f}", f"{row['gap']:+.2f}", row["surveys"], row["handle_label"]]
        for row in lists["bonus_top_5"]
    ]
    team_rows = [[row["team"], f"{row['closed']:,}", row["label"]] for row in summary["team_handle"]]
    month_rows = []
    for month in summary["csat"]["months"]:
        pulse = month["pulse2"]["csat"]
        other = month["other"]["csat"]
        month_rows.append(
            [
                month["month"],
                f"{month['all']['csat']:.2f}" if month["all"]["csat"] is not None else "",
                f"{pulse:.2f}" if pulse is not None else "",
                month["pulse2"]["surveys"],
                f"{other:.2f}" if other is not None else "",
                month["other"]["surveys"],
            ]
        )
    lot_bits = ", ".join(
        f"{row['lot_code']} {row['rate']*100:.0f}% ({row['replacements']}/{row['tickets']})"
        for row in summary["lots"]["lots"][:5]
    )
    base_rate = repl["baseline"]["rate"] * 100
    since_rate = repl["since_december"]["rate"] * 100
    early_det = det["jan_sep_2025"]["rate"] * 100
    late_det = det["jan_jun_2026"]["rate"] * 100
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Vireo scoreboard, Jan–Jun 2026</title>
<style>
  body {{ font: 15px/1.45 -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px auto; max-width: 980px; color: #1a1a1a; background: #fff; }}
  h1 {{ font-size: 28px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin-top: 32px; }}
  p, li {{ max-width: 68ch; }}
  .muted {{ color: #555; }}
  .box {{ background: #f6f3ea; padding: 14px 16px; border-left: 4px solid #8a5a00; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0 4px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #ddd; vertical-align: top; }}
  th {{ font-size: 12px; letter-spacing: 0.02em; color: #444; }}
  td:nth-child(n+3), th:nth-child(n+3) {{ text-align: right; }}
</style>
</head>
<body>
<h1>Who to coach, January–June 2026</h1>
<p class="muted">Average of surveys that were answered, scale 1 to 5. Blank surveys are left out. Time to finish is the median from the first human reply to resolution. Built by <code>score.py</code> from the files in <code>data/</code>. No model calls.</p>
<div class="box">
<p><strong>The number.</strong> Customers giving a 1 or a 2 rose from {early_det:.0f}% of answered surveys before October 2025 to {late_det:.0f}% in January–June 2026. Bringing the {lift['people']} people whose shortfall clears a rough confidence interval up to the level of similar tickets moves the company average by about {lift['mean_lift']:.2f} points, on {lift['surveys']} surveys out of {lift['company_surveys']:,}. It does not buy the drop from {late_det:.0f}% back to {early_det:.0f}%.</p>
<p>Pulse 2 replacements ran at {base_rate:.0f}% from launch through September 2025 and at {since_rate:.0f}% from December 2025 through June 2026. The extra replacements, at Rs {repl['each_inr']:,.0f} each (unit cost Rs {repl['unit_cost_inr']:,.0f} plus Rs {repl['logistics_inr']:,.0f} logistics), cost about Rs {repl['since_december']['excess_inr']:,.0f}. January–March 2026 alone was about Rs {repl['jan_mar_2026']['excess_inr']:,.0f}. April–June was about Rs {repl['apr_jun_2026']['excess_inr']:,.0f}.</p>
<p>Where the customer quoted an order, the October–December 2025 lots are the ones being replaced: {lot_bits}. {summary['lots']['pulse2_since_dec_without_order']:,} Pulse 2 tickets since December had no matching order, so they are in the rupee figure and not in that lot list.</p>
</div>
<h2>Raw bottom ten, by rating</h2>
<p class="muted">The sort Priya asked for. Warranty is on this list because those agents were given the Pulse 2 faults.</p>
{table(["Person", "Team", "Rating", "Surveys", "Time to finish"], raw_rows)}
<h2>Ten to look at after the ticket mix</h2>
<p class="muted">Rating minus the rating other agents got on the same product and the same problem type. Warranty is left off this list. A name is marked for coaching only when a rough 95% interval for that gap sits entirely below zero. The rest of this ten match their tickets, or the shortfall is too small to trust.</p>
{table(["Person", "Team", "Rating", "Similar tickets", "Gap", "Surveys", "Time to finish"], coach_rows)}
<h2>Diwali bonus, top five on the same comparison</h2>
<p class="muted">At least {MIN_SURVEYS} answered surveys. Warranty agents were eligible. None landed here.</p>
{table(["Person", "Team", "Rating", "Similar tickets", "Gap", "Surveys", "Time to finish"], bonus_rows)}
<h2>Time to finish, by team</h2>
{table(["Team", "Tickets closed", "Median time"], team_rows)}
<h2>Rating by month</h2>
<p class="muted">Company average before October 2025 was {csat['before_oct_2025']['csat']:.2f} ({csat['before_oct_2025']['surveys']:,} surveys). January–June 2026 was {csat['jan_jun_2026']['csat']:.2f} ({csat['jan_jun_2026']['surveys']:,} surveys).</p>
{table(["Month", "All products", "Pulse 2", "Pulse 2 surveys", "Other products", "Other surveys"], month_rows)}
<p class="muted">Peer averages used the same product and problem type when at least {MIN_PEERS} surveys from other agents existed ({summary['peer_fallback']['cell']:,} surveys). Otherwise the product ({summary['peer_fallback']['product']:,}), otherwise everyone ({summary['peer_fallback']['all']:,}).</p>
</body>
</html>
"""
    (OUT / "scoreboard.html").write_text(html, encoding="utf-8")


def build() -> dict:
    tickets = prepare(load_csv("tickets.csv"))
    agents = {row["agent_id"]: row for row in load_csv("agents.csv")}
    products = {row["sku"]: row for row in load_csv("products.csv")}
    orders = {row["order_id"]: row for row in load_csv("orders.csv")}
    names = [row["name"] for row in agents.values()]
    rows, fallback_counts, scored_n = agent_rows(tickets, agents)
    lists = select_lists(rows)
    summary = {
        "window": "2026-01-01 to 2026-06-30",
        "min_surveys": MIN_SURVEYS,
        "tickets": len(tickets),
        "legacy_negative_handles_before_shift": negative_handles(load_csv("tickets.csv"), shift_legacy=False),
        "legacy_negative_handles_after_shift": negative_handles(load_csv("tickets.csv"), shift_legacy=True),
        "duplicate_display_names": sorted(name for name in set(names) if names.count(name) > 1),
        "both_refund_and_replacement": both_refund_and_replacement(tickets),
        "csat": company_csat(tickets),
        "detractors": detractor_story(tickets),
        "replacements": replacement_story(tickets, products),
        "lots": lot_story(tickets, orders),
        "coaching_lift": coaching_lift(rows, lists, scored_n),
        "peer_fallback": fallback_counts,
        "team_handle": team_handle(tickets, agents),
        "lists": lists,
        "agents": rows,
    }
    return summary


def main() -> None:
    OUT.mkdir(exist_ok=True)
    summary = build()
    public = {key: value for key, value in summary.items() if key != "agents"}
    # Lists contain the same dicts as agents; json can handle them once.
    (OUT / "summary.json").write_text(json.dumps(public, indent=2), encoding="utf-8")
    write_agents_csv(summary["agents"])
    write_html(summary)
    det = summary["detractors"]
    repl = summary["replacements"]
    lift = summary["coaching_lift"]
    print(f"tickets {summary['tickets']}")
    print(f"detractors {det['jan_sep_2025']['rate']:.1%} -> {det['jan_jun_2026']['rate']:.1%}")
    print(f"pulse2 detractors in window {det['jan_jun_2026_pulse2']['rate']:.1%} other {det['jan_jun_2026_other']['rate']:.1%}")
    print(f"excess replacements since Dec {repl['since_december']['excess_replacements']} cost Rs {repl['since_december']['excess_inr']}")
    print(f"Jan-Mar excess Rs {repl['jan_mar_2026']['excess_inr']} rate {repl['jan_mar_2026']['rate']:.1%}")
    print(f"Apr-Jun excess Rs {repl['apr_jun_2026']['excess_inr']} rate {repl['apr_jun_2026']['rate']:.1%}")
    print(f"baseline rate {repl['baseline']['rate']:.1%} n {repl['baseline']['tickets']}")
    print(f"coaching lift {lift}")
    print("raw bottom", [row["agent_id"] for row in summary["lists"]["raw_bottom_10"]])
    print("material", [(row["agent_id"], row["name"], row["gap"], row["surveys"]) for row in summary["lists"]["coach_material"]])
    print("bonus", [(row["agent_id"], row["name"], row["gap"]) for row in summary["lists"]["bonus_top_5"]])
    print(f"wrote {OUT / 'scoreboard.html'}")


if __name__ == "__main__":
    main()
