# Assumptions Log

Every simulated number in this project comes from a rate listed here. Each is a stated assumption, not a measured fact. With a real firm's data, each row would be replaced by the measured value.

## Data assumptions

| # | Assumption | Why it is reasonable |
| --- | --- | --- |
| D1 | FARS fatal crashes are used as the **seasonal demand signal**, not as total injury volume | Fatal and injury crashes follow similar seasonal and geographic patterns; state injury data is added in Phase 2 |
| D2 | Monthly FARS counts are scaled up to injury-crash volume with a fixed ratio per state | Keeps the real seasonal shape while giving realistic lead volumes |
| D3 | Each office serves its home county | Keeps the market definition simple and auditable |
| D4 | Weather is averaged across GHCN-Daily stations within 25 km of each office; each measure uses only stations that report it for 15+ days of the month | Robust to single-station gaps; avoids rain-only stations counting as zero snow |

## Firm simulation assumptions

| # | Assumption | Value used |
| --- | --- | --- |
| S1 | Monthly leads per office | 120 × office market size (0.45 Savannah to 1.35 Houston) × crash demand index × trend × marketing effect. About 1,700 leads a month firm-wide |
| S2 | Lead-to-signed conversion | Base 16–26% by case type, lifted by fast callbacks and referrals; about 28–30% overall |
| S3 | Response-time effect (**planted**) | Leads called back within 5 minutes sign about 1.5× as often as leads called back after 1 hour |
| S4 | Winter effect (**planted**) | Michigan and Ohio auto leads rise in December–February with snowfall |
| S5 | Contingency fee | 33% pre-suit, 40% after suit is filed |
| S6 | Share of cases that go to suit | 15–30%, higher for truck and wrongful death |
| S7 | Settlement value | Lognormal by case type and state; truck and wrongful death highest |
| S8 | Time from sign to payment | Median 12–18 months; longer for truck and wrongful death |
| S9 | Marketing effect | $75,000 a month × market size, about $10M a year (about 11% of fees). Leads rise with spend^0.35 (diminishing returns). Campaigns: Houston TV from Mar 2021 (+60%), Atlanta digital from Sep 2023 (+50%) |
| S10 | Staff roles and capacity | Intake specialist 60 leads/month; case manager 70 open cases; demand writer 250 open cases; litigation paralegal 60 open suits; associate attorney 150 open cases. Staffed to 90% of trailing workload, with a 2–4 month hiring lag |
| S11 | Turnover effect (**planted**) | Case managers above 1.3× benchmark caseload leave about twice as often |
| S12 | Random seed | Fixed (42), so every run is reproducible |
| S13 | Firm history | Simulated from Jan 2013 so caseloads and payments are mature by 2017, the first year of public data. Analysis uses 2017 onward |
| S14 | Snapshot date | 31 Dec 2025. Cases not paid by then are Open, with no settlement yet |
| S15 | Lost cases | 8% of signed cases end with no recovery |
| S16 | Florida tort reform | Case values ×0.85 for Florida cases signed after 24 Mar 2023 |
| S17 | COVID | Leads ×0.70 / 0.75 / 0.85 in Apr / May / Jun 2020 (fewer minor crashes in lockdown) |
| S18 | Staff turnover | Base monthly quit rate 1.5–3.5% by role; ×1.4 in Jan–Mar (after bonuses), ×1.2 in Jul–Aug; ×1.3 when any role is overloaded |
| S19 | Loaded staff cost per hour (for case margin) | Case manager $45, associate attorney $150, litigation paralegal $40 |
| S20 | Case costs | The firm advances case costs (2-6% of settlement, plus $3k-15k if in suit). Won cases reimburse them from the settlement; lost cases are absorbed by the firm. Only absorbed costs reduce contribution margin |

## Known limitations

- FARS covers fatal crashes only, so absolute demand levels are estimates; seasonal shape and trend are the reliable parts.
- Premises liability, dog bite and workers' comp have no public crash signal. Their seasonality is simulated and stated as such.
- Firm results describe a simulated firm. The method, not the specific numbers, is what transfers to a real firm.
