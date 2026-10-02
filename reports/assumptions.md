# Assumptions Log

This document records every assumption used to simulate firm activity and estimate personal injury case demand.

Every simulated number in this project comes from a stated assumption below. These values are not measured results from a real law firm. If real firm data were available, each simulated input would be replaced with the corresponding measured value.

The assumptions are separated into public-data assumptions and firm-simulation assumptions so that the boundary between observed data and simulated data remains clear.

## Data Assumptions

| # | Assumption | Why It Is Reasonable |
| --- | --- | --- |
| D1 | FARS fatal crashes are used as the **seasonal demand signal**, not as total injury volume | Fatal and injury crashes follow similar seasonal and geographic patterns. State injury-crash data is planned for Phase 2. |
| D2 | Monthly FARS counts are scaled to estimated injury-crash volume using a fixed ratio per state | Preserves the seasonal shape of the public crash data while producing realistic lead volumes for the simulation. |
| D3 | Each office serves its home county | Keeps the market definition simple, consistent, and auditable. |
| D4 | Weather is averaged across GHCN-Daily stations within 25 km of each office. Each measure uses only stations that report it for at least 15 days of the month | Reduces sensitivity to individual station gaps and prevents stations that do not report snowfall from being treated as having zero snow. |

## Firm Simulation Assumptions

| # | Assumption | Value Used |
| --- | --- | --- |
| S1 | Monthly leads per office | 120 × office market size (0.45 Savannah to 1.35 Houston) × crash demand index × trend × marketing effect. This produces about 1,700 leads per month firm-wide. |
| S2 | Lead-to-signed conversion | Base conversion of 16–26% by case type, increased by faster callbacks and referrals. Overall conversion is approximately 28–30%. |
| S3 | Response-time effect (**planted**) | Leads called back within 5 minutes sign at approximately 1.5× the rate of leads called back after 1 hour. |
| S4 | Winter effect (**planted**) | Michigan and Ohio auto leads increase during December–February with snowfall. |
| S5 | Contingency fee | 33% before suit and 40% after suit is filed. |
| S6 | Share of cases that go to suit | 15–30%, with higher rates for truck and wrongful-death cases. |
| S7 | Settlement value | Settlement values follow a lognormal distribution by case type and state. Truck and wrongful-death cases have the highest values. |
| S8 | Time from sign to payment | Median duration of 12–18 months, with longer durations for truck and wrongful-death cases. |
| S9 | Marketing effect | Marketing spend is $75,000 per month × market size, or approximately $10 million per year and about 11% of fees. Leads increase with spend^0.35, representing diminishing returns. Campaigns include Houston TV beginning March 2021 (+60%) and Atlanta digital beginning September 2023 (+50%). |
| S10 | Staff roles and capacity | Intake specialist: 60 leads/month. Case manager: 70 open cases. Demand writer: 250 open cases. Litigation paralegal: 60 open suits. Associate attorney: 150 open cases. Staffing targets 90% of trailing workload with a 2–4 month hiring lag. |
| S11 | Turnover effect (**planted**) | Case managers above 1.3× benchmark caseload leave at approximately twice the normal rate. |
| S12 | Random seed | Fixed at 42 so every simulation run is reproducible. |
| S13 | Firm history | Firm activity is simulated from January 2013 so caseloads and payments are mature by 2017, the first year of the public crash data used in the analysis. Analysis uses 2017 onward. |
| S14 | Snapshot date | December 31, 2025. Cases that have not been paid by this date remain Open with no settlement recorded. |
| S15 | Lost cases | 8% of signed cases end with no recovery. |
| S16 | Florida tort reform | Case values are multiplied by 0.85 for Florida cases signed after March 24, 2023. |
| S17 | COVID impact | Leads are multiplied by 0.70, 0.75, and 0.85 in April, May, and June 2020 respectively to represent reduced minor-crash activity during lockdowns. |
| S18 | Staff turnover | Base monthly quit rate is 1.5–3.5% by role. The rate is multiplied by 1.4 in January–March, 1.2 in July–August, and 1.3 when any role is overloaded. |
| S19 | Loaded staff cost per hour | Case manager: $45/hour. Associate attorney: $150/hour. Litigation paralegal: $40/hour. These rates are used for case-margin calculations. |
| S20 | Case costs | The firm advances case costs equal to 2–6% of settlement value, plus $3,000–$15,000 when a case goes into suit. Won cases reimburse these costs from settlement proceeds. Lost cases are absorbed by the firm. Only absorbed costs reduce contribution margin. |

## Plant-and-Recover Assumptions

Several assumptions are intentionally planted into the simulation so the analytical pipeline can be tested.

These effects are not presented as measured findings from a real firm. They are known inputs used to validate whether the analysis can recover relationships that were intentionally introduced into the simulated data.

| Planted Effect | Simulation Rule | Validation Purpose |
| --- | --- | --- |
| Response time | Callback within 5 minutes produces approximately 1.5× the signing rate of a callback after 1 hour | Tests whether intake-response speed can be detected in the analysis |
| Winter auto demand | Michigan and Ohio auto leads increase during December–February with snowfall | Tests whether weather-related seasonal patterns can be recovered |
| Caseload and turnover | Case managers above 1.3× benchmark caseload leave at approximately twice the normal rate | Tests whether workload pressure is reflected in turnover patterns |

A fixed random seed of **42** is used so that the same inputs produce reproducible results across runs.

## Known Limitations

### FARS is a demand signal, not a complete injury dataset

FARS covers fatal crashes only. It is therefore not a direct measure of total personal injury demand.

The absolute demand levels generated from FARS are estimates. The seasonal shape and geographic patterns are the more reliable components of the signal.

### Some case types do not have a public crash signal

Premises liability, dog bite, and workers' compensation cases do not have a comparable public crash-based demand signal in this project.

Their seasonality is therefore simulated and explicitly treated as an assumption rather than an observed relationship.

### Firm results are simulated

The law firm activity in this project is simulated.

The specific lead counts, signed cases, settlement values, staffing levels, revenue, and margins should not be interpreted as actual results from a real law firm.

The transferable part of the project is the **methodology**:

- separating market demand from firm capture
- using external demand signals for forecasting
- measuring intake and conversion
- connecting demand forecasts to staffing
- connecting signed cases to revenue timing
- evaluating office performance relative to market conditions

## Interpretation Rule

Throughout the project, public data and simulated firm data should be interpreted differently:

- **Public data** provides the external demand, weather, and population signals.
- **Simulated data** represents firm leads, cases, payments, marketing, staffing, and operating activity.
- **Planted effects** are known relationships intentionally introduced into the simulation for validation.
- **Forecasts and business metrics** are outputs of the analytical pipeline and should be interpreted within these assumptions and limitations.

This distinction is maintained throughout the SQL transformations, validation tests, forecasting analysis, and Looker Studio dashboard.