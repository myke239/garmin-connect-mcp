# Recovery and performance research

[Documentation home](../README.md) · [Coaching guide](../guides/coaching.md)

Research date: 2026-10-16. Priority: strength training, with shared physiology and
nutrition support for endurance. This is an engineering evidence review, not a
systematic review or an exhaustive claim about every Garmin scalar/API field.
Device, firmware, subscription, sensor and region affect availability. A metric
in Connect is not proof of SDK access, connector support or validity for an
individual prediction. Official partner Health API access is distinct from this
connector's unofficial authenticated API.

## Metric inventory and importance

The [pinned SDK getter inventory](../reference/catalogs/garmin-sdk-read-inventory.json)
records every public get_* method and signature in garminconnect 0.3.17 without
contacting an account. This is a bounded SDK capability inventory, not a list of
enabled tools. Feature families below organize the research coverage. Arbitrary
SDK methods are never exposed through an endpoint/tool dispatcher.

| Family | Relevant metrics | Interpretation and limits | Current analysis |
| --- | --- | --- | --- |
| Heart rate | Resting, average/night, minimum/maximum, activity HR, zones, recovery HR | Internal response; optical errors, heat, medications and exertion confound HR | Dated resting HR collected; existing activity tools supply exercise context |
| HRV | Overnight average, short-window peaks, seven-day trend, personal baseline/status; beat intervals where available | Autonomic context; measurement definition and personal trend matter; high is not always better | Overnight average collected; personal descriptive range, no diagnosis |
| Sleep quantity | Duration, naps, timing, awakenings, consistency, sleep need | Recovery opportunity and schedule; device staging differs from clinical sleep measurement | Duration collected; other data remains source-specific |
| Sleep quality | Score, stages, sleep stress, breathing variations, sleep alignment | Vendor estimates; score overlaps physiology and cannot establish sleep disorder | Score collected; no stage-based causal model |
| Respiration/oxygen | Sleep/waking rate, Pulse Ox, breathing variations | Context for unusual trends, altitude, sensor fit; not illness or sleep-apnea diagnosis | Sleep respiration collected; explicit-unit SpO2 input accepted, no automatic normalization yet |
| Temperature | Skin-temperature deviation | Peripheral measurement relative to personal baseline, not core temperature | Explicit deviation input accepted; collector mapping not established |
| Daily stress | Stress score/timeline, rest/low/medium/high duration | Physiological stress estimate, not a direct psychological measurement | Dated average stress collected; sentinels excluded |
| Energy composites | Body Battery, charge/drain, readiness, recovery time | Shared HRV/sleep/stress inputs; not independent votes; recovery time concerns next hard training | Morning readiness only when confirmed; other composites contextual |
| Activity and energy | Steps, floors, wheelchair pushes, intensity minutes, sedentary time, distance, active/resting/total calories | Daily movement/exposure; expenditure is estimated, not measured metabolic balance | Existing daily/activity tools; no calorie subtraction model |
| Aerobic capacity | VO2 max, fitness age, threshold HR/pace, FTP, race predictions | Capacity estimates, often sport specific; stale measurements must be labeled | Existing recovery tools; no conversion into strength readiness |
| Training demand | Exercise/EPOC load, acute/chronic load, load focus/ratio, aerobic/anaerobic effect, status | Internal cardiovascular load; not local mechanical stress or injury probability | Acute-load input supported; existing training-status context retained |
| Mechanical running | Impact load/tolerance, cadence, stride, ground contact, vertical oscillation/ratio, balance, power | Technique/exposure context; depends on devices and terrain, not tissue diagnosis | Research/integration backlog; no invented fatigue conversion |
| Endurance performance | Pace/speed/power, time, distance, laps, elevation, stamina, performance condition, endurance/hill scores | Compare matching terrain, conditions and task; in-session indicators differ from pre-session forecasts | Existing activity analysis and new historical-reference tool |
| Cycling/swimming/other sports | Power/cadence, dynamics, FTP; stroke rate/count, SWOLF, pool length; sport-specific splits | Task-specific history; avoid merging unlike sports into one performance target | Existing sources; detailed models deferred for strength priority |
| Strength | Exact movement/equipment, work/warmup sets, reps, external load, rest, duration, exercise order | Local task specificity; raw SDK weights lack confirmed read units in current normalizer | New regional exposure, exact-equipment and sequence analysis; unverified weight remains null |
| Effort/neuromuscular | RIR/RPE, velocity loss, warmup performance, region-specific soreness/pain | Important strength context; generally user or extra-sensor inputs, not inferred from HRV | RIR/check-in input; velocity modeling deferred |
| Body composition | Weight, BMI, fat %, skeletal muscle, water %, bone mass and visceral-fat estimates where available | Scale estimates affected by conditions; trends/context, not precise tissue change | Existing measurement sources; no body-composition health score |
| Other health | Blood pressure/pulse, Health Snapshot, ECG where supported, menstrual/pregnancy logs | Manual/device-specific; sensitive context; not all SDK-accessible or appropriate for prediction | Existing blood-pressure read; remaining sources require separate verification |
| Nutrition | Energy, protein, carbohydrate, fat, sugar/sodium and other logged nutrients, goals, meal detail | Logged intake can be incomplete; meal labels are not timing; targets are not requirements | MFP totals/goals/completion projection; four core nutrients analyzed |
| Hydration | Logged fluid, estimated sweat loss where supported | Intake does not establish fluid balance or electrolyte status | Existing Garmin/MFP water reads; hydration inference deferred |
| Lifestyle/environment | Alcohol/caffeine/custom fields, medication logs, travel, work stress, weather/heat/altitude, acclimation | Time alignment/confounding; medicine quantities never imply dose recommendations | Lifestyle read tools and exploratory lagged presence comparison; environment models deferred |

Garmin's [Health API](https://developer.garmin.com/gc-developer-program/health-api/)
documents major daily health families and partner-access requirements. Its
[HRV explanation](https://www.garmin.com/en-CA/blog/fitness/understanding-the-hrv-status-on-your-garmin-smartwatch/)
describes overnight measurement and personal baseline establishment. Its
[readiness manual](https://www8.garmin.com/manuals/webhelp/GUID-31D23DBB-57C2-4DF7-A0C9-8D1A00AB4BE7/EN-GB/GUID-C21BE0C8-A08E-4DA1-B6C6-2E0E2DDDB372.html)
shows overlapping sleep, HRV, recovery and load inputs. A product description
establishes intended meaning, not independent prediction validity.

## Evidence-to-design decisions

| Evidence | Design consequence | What it does not establish |
| --- | --- | --- |
| [Athlete self-report review](https://pubmed.ncbi.nlm.nih.gov/26423706/) | Include symptoms, fatigue, soreness and perceived recovery alongside physiology | A universally valid subjective readiness threshold |
| [HRV-guided endurance trial](https://pubmed.ncbi.nlm.nih.gov/26909534/) | Explore personal HRV-guided endurance decisions separately | Exact repetition forecasts, injury probability or strength readiness from HRV |
| [Strength autoregulation review](https://pubmed.ncbi.nlm.nih.gov/33520457/) | Prefer exercise-specific effort and performance context to a fixed readiness multiplier | Validity of the present software as a calibrated prescription model |
| [RIR fatigue experiment](https://pubmed.ncbi.nlm.nih.gov/36752989/) | Retain proximity-to-failure and regional/exercise specificity; distinguish missing RIR | Universal 24/48-hour recovery deadlines; applicability beyond the tested protocol |
| [Nutrition position statement](https://pubmed.ncbi.nlm.nih.gov/26891166/) | Include intake, timing where available, training demands and professional context | Individual glycogen or energy availability from food/wearable calories alone |
| [Sleep consensus](https://pubmed.ncbi.nlm.nih.gov/33144349/) | Review sleep history and individual needs; disclose uncertain effect sizes | A fixed performance percentage lost per hour of poor sleep |
| [Load-ratio critique](https://pubmed.ncbi.nlm.nih.gov/32502973/) | Keep loads descriptive; no ACWR-based injury probability | A universal safe/danger band for a particular person |
| [IOC REDs consensus](https://bjsm.bmj.com/content/57/17/1073) | Avoid diagnosing low energy availability or REDs from these inputs | Wearable/food diary measures as a clinical diagnostic assessment |

The software's p10/p90 baselines, 14-day observation minimum, five completed
outcomes, seven lifestyle days/group, 0–2 RIR grouping and 24/48/72-hour windows
are explicit engineering/display choices. They have not been clinically
validated. No weighted health score or calibrated success probability is shipped.

## Combining information

1. Systemic recovery: dated personal HRV/resting HR/respiration and sleep trends,
   check-in and original Garmin context, accounting for shared inputs.
2. Local strength exposure: exact exercise/equipment, work sets, elapsed hours,
   reported RIR and regional soreness/pain. Region overlap is descriptive and
   does not quantify recruitment. Planned exercise order identifies overlapping
   exposure, without pretending to know a numerical fatigue penalty.
3. Nutrition: compare logged totals with diary goals, retaining completeness,
   missing nutrients and date boundaries. Do not add imported exercise calories.
   Nutrient timing, hydration sufficiency, glycogen and energy availability are
   unknown unless independently established.
4. Lifestyle: compare explicit presence with explicit zero at a chosen lag;
   missing logs stay unknown. No causal inference, dose-response claim or
   medication recommendation. Account for training/nutrition/sleep confounding
   before deciding a pattern is useful to investigate.
5. Task outcome: compare genuinely matched prior sessions; report descriptive
   ranges and noncompletion counts. Different equipment/load/ROM/sequence cannot
   be pooled merely because movement labels resemble each other.

## Development gates

- Foundation: synthetic tests for numerical validity, units, timezone/date
  alignment, missing versus zero, duplicate evidence and future leakage.
- Source integration: bounded allowlisted Garmin normalization; MFP response
  projections through the caller's existing connector. No shared credential
  store, arbitrary URLs, account writes or personal-data fixtures.
- Strength evidence: preserve warmup/work-set distinction and exact exercise
  identity; never convert `garmin_raw_unverified` to kg. Current legacy set reads
  do not expose set timestamps or RIR; request independent evidence or omit them.
- Prospective evaluation (not yet complete): define outcomes, save explicit
  opt-in as-of snapshots separately from source, accumulate representative
  sessions and compare against a historical-median baseline on chronological
  held-out data. Report errors/interval coverage, abstention and sport/exercise
  subgroup failures. Retrospective lookups cannot establish prospective accuracy.
- Later models: only after evaluation consider conditional rep/load ranges,
  sequence effects, personalized recovery trajectories and adjusted lifestyle
  associations. Account for selection bias, autocorrelation, missingness and
  changes in devices/training/medication. Publish model/version limitations.

No attempt is made to enumerate every possible metric combination: combinations
need a defined hypothesis/outcome and sufficient quality data, rather than an
unbounded search for correlations.
