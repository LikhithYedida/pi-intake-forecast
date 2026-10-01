# Assumptions Log

Every simulated number in this project comes from a rate listed here. Each is a stated assumption, not a measured fact. With a real firm's data, each row would be replaced by the measured value.

## Data assumptions

| # | Assumption | Why it is reasonable |
| --- | --- | --- |
| D1 | FARS fatal crashes are used as the **seasonal demand signal**, not as total injury volume | Fatal and injury crashes follow similar seasonal and geographic patterns; state injury data is added in Phase 2 |
| D2 | Monthly FARS counts are scaled up to injury-crash volume with a fixed ratio per state | Keeps the real seasonal shape while giving realistic lead volumes |
| D3 | Each office serves its home county | Keeps the market definition simple and auditable |
| D4 | Weather comes from the GHCN-Daily station nearest each county center | Standard practice for county-level weather features |

## Firm simulation assumptions

| # | Assumption | Value used |
| --- | --- | --- |
| S1 | Leads per injury crash in the firm's county | Set per state so each office averages a realistic monthly lead volume |
| S2 | Lead-to-signed conversion | 20–35%, by case type |
| S3 | Response-time effect (**planted**) | Leads called back within 5 minutes sign about 1.5× as often as leads called back after 1 hour |
| S4 | Winter effect (**planted**) | Michigan and Ohio auto leads rise in December–February with snowfall |
| S5 | Contingency fee | 33% pre-suit, 40% after suit is filed |
| S6 | Share of cases that go to suit | 15–30%, higher for truck and wrongful death |
| S7 | Settlement value | Lognormal by case type and state; truck and wrongful death highest |
| S8 | Time from sign to payment | Median 12–18 months; longer for truck and wrongful death |
| S9 | Marketing effect | Diminishing returns on monthly spend per market |
| S10 | Staff roles | Intake specialist, case manager, demand writer, litigation paralegal, associate attorney |
| S11 | Turnover effect (**planted**) | Case managers above 1.3× benchmark caseload leave about twice as often |
| S12 | Random seed | Fixed (42), so every run is reproducible |

## Known limitations

- FARS covers fatal crashes only, so absolute demand levels are estimates; seasonal shape and trend are the reliable parts.
- Premises liability, dog bite and workers' comp have no public crash signal. Their seasonality is simulated and stated as such.
- Firm results describe a simulated firm. The method, not the specific numbers, is what transfers to a real firm.