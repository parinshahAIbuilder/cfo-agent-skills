#!/usr/bin/env python3
"""Loan Offer True-Cost Comparator.

Usage:
    python3 loan_cost.py offers.json            # prints JSON results
    python3 loan_cost.py offers.json --csv out  # also writes out_schedule_<name>.csv

offers.json:
{
  "offers": [
    {"name": "Bank A", "principal": 1000000, "annual_rate": 10.5, "tenure_months": 60,
     "rate_type": "reducing",              # reducing | flat
     "processing_fee_pct": 1.0,            # % of principal, deducted upfront
     "processing_fee_flat": 0,             # fixed upfront fee
     "fee_tax_pct": 18,                    # GST/VAT on fees (0 if none)
     "insurance_upfront": 0,               # bundled insurance/other upfront charges
     "other_monthly_charges": 0,
     "moratorium_months": 0,               # interest-only months before EMIs
     "prepay_month": null,                 # optional: month of full prepayment
     "prepay_penalty_pct": 0}              # % of outstanding at prepayment
  ]
}
Standard library only.
"""
import json, sys, csv


def emi_reducing(p, r_m, n):
    if r_m == 0:
        return p / n
    return p * r_m * (1 + r_m) ** n / ((1 + r_m) ** n - 1)


def irr_monthly(cfs):
    """Bisection IRR on monthly cash flows (cfs[0] at t=0)."""
    def npv(r):
        return sum(cf / (1 + r) ** t for t, cf in enumerate(cfs))
    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def analyse(o):
    P = float(o["principal"])
    rate = float(o["annual_rate"]) / 100
    n = int(o["tenure_months"])
    mor = int(o.get("moratorium_months", 0) or 0)
    fee = P * float(o.get("processing_fee_pct", 0) or 0) / 100 + float(o.get("processing_fee_flat", 0) or 0)
    fee *= 1 + float(o.get("fee_tax_pct", 0) or 0) / 100
    upfront = fee + float(o.get("insurance_upfront", 0) or 0)
    monthly_other = float(o.get("other_monthly_charges", 0) or 0)
    r_m = rate / 12
    rtype = o.get("rate_type", "reducing")

    schedule = []
    bal = P
    m = 0
    for _ in range(mor):  # interest-only moratorium
        m += 1
        interest = bal * r_m
        schedule.append([m, round(bal, 2), round(interest, 2), 0.0, round(interest + monthly_other, 2), round(bal, 2)])

    if rtype == "flat":
        total_int = P * rate * n / 12
        emi = (P + total_int) / n
        int_part = total_int / n
        for _ in range(n):
            m += 1
            open_b = bal
            prin = emi - int_part
            bal -= prin
            schedule.append([m, round(open_b, 2), round(int_part, 2), round(prin, 2), round(emi + monthly_other, 2), round(max(bal, 0), 2)])
    else:
        emi = emi_reducing(P, r_m, n)
        for _ in range(n):
            m += 1
            open_b = bal
            interest = bal * r_m
            prin = emi - interest
            bal -= prin
            schedule.append([m, round(open_b, 2), round(interest, 2), round(prin, 2), round(emi + monthly_other, 2), round(max(bal, 0), 2)])

    prepay_m = o.get("prepay_month")
    penalty = 0.0
    if prepay_m:
        prepay_m = int(prepay_m)
        row = schedule[prepay_m - 1]
        outstanding = row[5]
        penalty = outstanding * float(o.get("prepay_penalty_pct", 0) or 0) / 100
        schedule = schedule[:prepay_m]
        schedule[-1][4] = round(schedule[-1][4] + outstanding + penalty, 2)
        schedule[-1][5] = 0.0

    payments = [row[4] for row in schedule]
    cfs = [P - upfront] + [-p for p in payments]
    irr = irr_monthly(cfs)
    apr = irr * 12 * 100 if irr is not None else None
    eff_annual = ((1 + irr) ** 12 - 1) * 100 if irr is not None else None
    total_paid = sum(payments) + upfront
    return {
        "name": o.get("name", "Offer"),
        "headline_rate_pct": float(o["annual_rate"]),
        "rate_type": rtype,
        "emi": round(emi, 2),
        "net_disbursed": round(P - upfront, 2),
        "upfront_charges": round(upfront, 2),
        "total_interest": round(sum(r[2] for r in schedule), 2),
        "prepayment_penalty": round(penalty, 2),
        "total_outflow": round(total_paid, 2),
        "total_cost_of_credit": round(total_paid - P, 2),
        "true_apr_pct": round(apr, 3) if apr is not None else None,
        "effective_annual_rate_pct": round(eff_annual, 3) if eff_annual is not None else None,
        "months": len(schedule),
        "_schedule": schedule,
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    data = json.load(open(sys.argv[1]))
    results = [analyse(o) for o in data["offers"]]
    results.sort(key=lambda r: (r["true_apr_pct"] is None, r["true_apr_pct"]))
    if "--csv" in sys.argv:
        prefix = sys.argv[sys.argv.index("--csv") + 1]
        for r in results:
            fn = f"{prefix}_schedule_{r['name'].replace(' ', '_')}.csv"
            with open(fn, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["month", "opening_balance", "interest", "principal", "payment", "closing_balance"])
                w.writerows(r["_schedule"])
    for r in results:
        r.pop("_schedule")
    print(json.dumps({"ranked_by_true_apr": results}, indent=2))


if __name__ == "__main__":
    main()
