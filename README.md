# CFO Agent Skills

Six Claude / agent skills (SKILL.md format) for CFOs, treasury teams, founders and investors — written by a listed-company CFO (CA, CPA) who has taken a company from startup to main-board IPO, raised listed NCDs and bank debt, and signed the covenant certificates.

| Skill | What it does |
|---|---|
| [debt-covenant-dscr-monitor](debt-covenant-dscr-monitor/SKILL.md) | Tests financials against loan/NCD covenants (DSCR, ICR, Debt/EBITDA, TOL/TNW, FACR), shows headroom and EBITDA cushion, drafts the compliance certificate and waiver request. Python engine included. |
| [credit-rating-readiness](credit-rating-readiness/SKILL.md) | Scores business and financial risk like a rating agency, estimates an indicative band, quantifies the levers for an upgrade and builds the agency pack. |
| [audit-pbc-auditor-query-responder](audit-pbc-auditor-query-responder/SKILL.md) | Builds a tailored PBC tracker and drafts evidence-backed replies to auditor queries and management letter points (Ind AS, IFRS, US GAAP, CARO 2020). |
| [cap-table-dilution-simulator](cap-table-dilution-simulator/SKILL.md) | Models SAFE/note conversion, option-pool shuffle and new money round by round, plus an exit waterfall. Python engine included. |
| [loan-offer-true-cost-comparator](loan-offer-true-cost-comparator/SKILL.md) | Ranks loan offers by true APR after flat rates, fees, tax on fees, insurance and prepayment penalties. Python calculator included. |
| [startup-term-sheet-reviewer](startup-term-sheet-reviewer/SKILL.md) | Reviews a term sheet, SAFE, note or CCPS clause by clause, models founder take-home and drafts a counter-proposal email. |

## Install

Copy any skill folder into your agent's skills directory (for Claude Code: `~/.claude/skills/<skill-name>/`). Scripts use the Python standard library only.

## Disclaimer

Commercial and analytical tooling only — not legal, tax or investment advice.

## Author

Parin Shah — CFO | CA, CPA — [LinkedIn](https://www.linkedin.com/in/parinshah-cfo)

## License

MIT
