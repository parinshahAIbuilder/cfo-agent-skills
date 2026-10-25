#!/usr/bin/env python3
"""Cap Table & Dilution Simulator.

Usage: python3 cap_table.py captable.json [--csv prefix]

captable.json:
{
  "holders": [ {"name": "Founder A", "class": "common", "shares": 6000000},
               {"name": "ESOP (granted+unallocated)", "class": "esop", "shares": 1000000} ],
  "safes":   [ {"name": "Angel SAFE", "amount": 500000, "cap": 8000000, "discount_pct": 20,
                "type": "post"} ],             # post (YC post-money) | pre
  "notes":   [ {"name": "Note 1", "amount": 200000, "rate_pct": 8, "months": 18,
                "cap": 6000000, "discount_pct": 20} ],
  "rounds":  [ {"name": "Series Seed", "pre_money": 10000000, "investment": 2500000,
                "pool_target_pct": 10,          # post-round ESOP target, topped up pre-money
                "investors": [{"name": "Lead VC", "amount": 2000000}, {"name": "Co-investor", "amount": 500000}]} ],
  "exits":   [ 20000000, 60000000 ],
  "liq_pref": {"multiple": 1, "participating": false}
}
Convertibles convert in the FIRST round. Standard library only.
Simplification: one preferred series per round, pari passu, no participation cap.
"""
import json, sys, csv


def fd(table):
    return sum(h["shares"] for h in table)


def run(cfg):
    table = [dict(h) for h in cfg["holders"]]
    log = []
    snapshots = [("Current", [dict(h) for h in table])]
    prefs = []  # (holder name, invested, shares)
    for i, rnd in enumerate(cfg.get("rounds", [])):
        pre = float(rnd["pre_money"]); inv = float(rnd["investment"])
        post = pre + inv
        existing = fd(table)
        esop_existing = sum(h["shares"] for h in table if h["class"] == "esop")
        pool_target = float(rnd.get("pool_target_pct", 0) or 0) / 100

        conv = []
        if i == 0:
            for s in cfg.get("safes", []):
                conv.append(("safe", s, float(s["amount"])))
            for n in cfg.get("notes", []):
                amt = float(n["amount"]) * (1 + float(n.get("rate_pct", 0)) / 100 * float(n.get("months", 0)) / 12)
                conv.append(("note", n, amt))

        # Iterate: price depends on pool top-up and convertible shares (pre-money method).
        new_pool = 0.0; conv_shares = {}
        for _ in range(200):
            pre_fd = existing + new_pool + sum(conv_shares.values())
            price = pre / pre_fd
            post_shares_inv = inv / price
            total_post = pre_fd + post_shares_inv
            # pool top-up so pool = target % of post
            target_pool = pool_target * total_post
            new_pool_next = max(0.0, target_pool - esop_existing)
            cs = {}
            for kind, c, amt in conv:
                p_disc = price * (1 - float(c.get("discount_pct", 0) or 0) / 100)
                cap = c.get("cap")
                if cap:
                    if kind == "safe" and c.get("type", "post") == "post":
                        # Company Capitalization: existing FD + all converting securities,
                        # excluding the pool top-up made for this round (YC post-money SAFE)
                        cap_base = existing + sum(conv_shares.values())
                        p_cap = float(cap) / cap_base
                    else:
                        p_cap = float(cap) / existing
                    p_conv = min(p_disc, p_cap)
                else:
                    p_conv = p_disc
                cs[c["name"]] = amt / p_conv
            if abs(new_pool_next - new_pool) < 0.5 and all(abs(cs[k] - conv_shares.get(k, 0)) < 0.5 for k in cs):
                new_pool, conv_shares = new_pool_next, cs
                break
            new_pool, conv_shares = new_pool_next, cs

        pre_fd = existing + new_pool + sum(conv_shares.values())
        price = pre / pre_fd
        if new_pool > 0:
            pool = next((h for h in table if h["class"] == "esop"), None)
            if pool: pool["shares"] += new_pool
            else: table.append({"name": "ESOP pool", "class": "esop", "shares": new_pool})
        for kind, c, amt in conv:
            sh = conv_shares[c["name"]]
            table.append({"name": c["name"], "class": f"pref-{rnd['name']}", "shares": sh})
            prefs.append((c["name"], amt, sh))
        for inv_ in rnd["investors"]:
            sh = float(inv_["amount"]) / price
            table.append({"name": inv_["name"], "class": f"pref-{rnd['name']}", "shares": sh})
            prefs.append((inv_["name"], float(inv_["amount"]), sh))
        effective_pre = pre - new_pool * price - sum(conv_shares.values()) * price
        log.append({"round": rnd["name"], "price_per_share": round(price, 6),
                    "pre_money_stated": pre, "post_money": post,
                    "pool_topup_shares": round(new_pool), "pool_topup_value": round(new_pool * price),
                    "convertible_shares": {k: round(v) for k, v in conv_shares.items()},
                    "effective_pre_money_for_existing_holders": round(effective_pre)})
        snapshots.append((rnd["name"], [dict(h) for h in table]))

    # waterfall
    lp = cfg.get("liq_pref", {"multiple": 1, "participating": False})
    mult = float(lp.get("multiple", 1)); part = bool(lp.get("participating", False))
    total = fd(table)
    exits = []
    for ev in cfg.get("exits", []):
        ev = float(ev)
        payout = {h["name"]: 0.0 for h in table}
        if not prefs:
            for h in table: payout[h["name"]] = ev * h["shares"] / total
        elif part:
            pref_total = sum(a * mult for _, a, _ in prefs)
            paid = min(ev, pref_total)
            for n, a, _ in prefs: payout[n] += paid * (a * mult) / pref_total
            rest = ev - paid
            for h in table: payout[h["name"]] += rest * h["shares"] / total
        else:
            # non-participating: each preferred holder takes max(pref, as-converted); solve by iteration
            converting = set()
            for _ in range(50):
                pref_hold = [(n, a, s) for n, a, s in prefs if n not in converting]
                pref_total = sum(a * mult for _, a, _ in pref_hold)
                paid = min(ev, pref_total)
                rest = ev - paid
                conv_sh = total - sum(s for _, _, s in pref_hold)
                ps = rest / conv_sh if conv_sh else 0
                newly = {n for n, a, s in pref_hold if s * ps > a * mult}
                if not newly: break
                converting |= newly
            for h in table:
                pref_entry = next((p for p in pref_hold if p[0] == h["name"]), None)
                if pref_entry:
                    payout[h["name"]] = paid * (pref_entry[1] * mult) / pref_total if pref_total else 0
                else:
                    payout[h["name"]] = h["shares"] * ps
        exits.append({"exit_value": ev, "payouts": {k: round(v) for k, v in payout.items()}})

    def snap(t):
        T = fd(t)
        return [{"name": h["name"], "class": h["class"], "shares": round(h["shares"]),
                 "pct_fd": round(100 * h["shares"] / T, 3)} for h in t]
    return {"rounds": log, "cap_tables": {n: snap(t) for n, t in snapshots}, "exit_waterfalls": exits}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    out = run(json.load(open(sys.argv[1])))
    if "--csv" in sys.argv:
        pre = sys.argv[sys.argv.index("--csv") + 1]
        for n, rows in out["cap_tables"].items():
            with open(f"{pre}_{n.replace(' ', '_')}.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["name", "class", "shares", "pct_fd"]); w.writeheader(); w.writerows(rows)
    print(json.dumps(out, indent=2))
