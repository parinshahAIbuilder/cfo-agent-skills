#!/usr/bin/env python3
"""Debt Covenant & DSCR Monitor.

Usage: python3 covenants.py input.json [--csv out.csv]

input.json:
{
  "currency": "INR crore",
  "periods": [
    {"period": "FY26", "revenue": 180, "ebitda": 54, "depreciation": 12, "interest": 14,
     "tax": 6, "pat": 22, "principal_repaid": 20, "lease_payments": 0,
     "total_debt": 210, "cash": 25, "net_worth": 160, "intangibles": 5,
     "total_outside_liabilities": 260, "current_assets": 90, "current_liabilities": 70,
     "net_fixed_assets_secured": 300}
  ],
  "covenants": [
    {"name": "DSCR", "metric": "dscr", "op": ">=", "threshold": 1.25},
    {"name": "Net debt / EBITDA", "metric": "net_debt_to_ebitda", "op": "<=", "threshold": 3.0},
    {"name": "Interest cover", "metric": "icr", "op": ">=", "threshold": 2.5},
    {"name": "TOL / TNW", "metric": "tol_tnw", "op": "<=", "threshold": 3.0},
    {"name": "Current ratio", "metric": "current_ratio", "op": ">=", "threshold": 1.1},
    {"name": "FACR", "metric": "facr", "op": ">=", "threshold": 1.5}
  ]
}
Metrics: dscr (cash-accrual basis: (PAT + depreciation + interest) / (interest + principal + lease)),
dscr_ebitda ((EBITDA - tax) / (interest + principal + lease)), icr (EBITDA / interest),
debt_to_ebitda, net_debt_to_ebitda, debt_equity, tol_tnw, current_ratio,
facr (secured net fixed assets / total debt). Standard library only.
"""
import json, sys, csv

OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


def g(p, k):
    return float(p.get(k, 0) or 0)


def div(a, b):
    return a / b if b else None


def metrics(p):
    debt_service = g(p, "interest") + g(p, "principal_repaid") + g(p, "lease_payments")
    tnw = g(p, "net_worth") - g(p, "intangibles")
    return {
        "dscr": div(g(p, "pat") + g(p, "depreciation") + g(p, "interest"), debt_service),
        "dscr_ebitda": div(g(p, "ebitda") - g(p, "tax"), debt_service),
        "icr": div(g(p, "ebitda"), g(p, "interest")),
        "debt_to_ebitda": div(g(p, "total_debt"), g(p, "ebitda")),
        "net_debt_to_ebitda": div(g(p, "total_debt") - g(p, "cash"), g(p, "ebitda")),
        "debt_equity": div(g(p, "total_debt"), g(p, "net_worth")),
        "tol_tnw": div(g(p, "total_outside_liabilities"), tnw),
        "current_ratio": div(g(p, "current_assets"), g(p, "current_liabilities")),
        "facr": div(g(p, "net_fixed_assets_secured"), g(p, "total_debt")),
    }


def ebitda_cushion(p, cov):
    """% EBITDA can fall before breach (EBITDA-driven metrics only), holding other items constant.
    For cash-accrual DSCR, a fall in EBITDA is assumed to flow through PAT (pre-tax-shield, conservative)."""
    m, op, t = cov["metric"], cov["op"], float(cov["threshold"])
    e = g(p, "ebitda")
    if e <= 0:
        return None
    ds = g(p, "interest") + g(p, "principal_repaid") + g(p, "lease_payments")
    if m == "icr" and g(p, "interest"):
        need = t * g(p, "interest")
    elif m == "dscr_ebitda":
        need = t * ds + g(p, "tax")
    elif m == "dscr":
        accr = g(p, "pat") + g(p, "depreciation") + g(p, "interest")
        need_accr = t * ds
        return round(100 * (accr - need_accr) / e, 1)
    elif m == "debt_to_ebitda":
        need = g(p, "total_debt") / t
    elif m == "net_debt_to_ebitda":
        need = (g(p, "total_debt") - g(p, "cash")) / t
    else:
        return None
    return round(100 * (e - need) / e, 1)


def run(cfg):
    rows = []
    for p in cfg["periods"]:
        ms = metrics(p)
        for c in cfg["covenants"]:
            v = ms.get(c["metric"])
            t = float(c["threshold"])
            if v is None:
                status, headroom = "N/A", None
            else:
                ok = OPS[c["op"]](v, t)
                headroom = (v - t) / t * 100 if c["op"] in (">=", ">") else (t - v) / t * 100
                status = "BREACH" if not ok else ("AMBER" if headroom < 10 else "GREEN")
            rows.append({"period": p["period"], "covenant": c["name"], "metric": c["metric"],
                         "actual": round(v, 2) if v is not None else None, "test": f"{c['op']} {t}",
                         "headroom_pct": round(headroom, 1) if headroom is not None else None,
                         "status": status, "ebitda_cushion_pct": ebitda_cushion(p, c)})
    return {"currency": cfg.get("currency", ""), "results": rows,
            "all_metrics": {p["period"]: {k: (round(v, 2) if v is not None else None) for k, v in metrics(p).items()} for p in cfg["periods"]}}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    out = run(json.load(open(sys.argv[1])))
    if "--csv" in sys.argv:
        fn = sys.argv[sys.argv.index("--csv") + 1]
        with open(fn, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out["results"][0].keys())); w.writeheader(); w.writerows(out["results"])
    print(json.dumps(out, indent=2))
