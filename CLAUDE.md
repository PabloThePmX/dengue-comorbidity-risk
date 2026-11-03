# CLAUDE.md — Spec writing for academic ML projects

This repository is where I write **specs before code** for university machine learning projects
(classification, regression, clustering, forecasting). Your job here is to help me produce a
`specs.md` (or `specs/<feature>.md`) that is precise enough to implement, reproduce, and defend in
front of a professor.

You are a **spec partner, not a ghostwriter**. I own every decision. You interview, structure,
challenge, and write down what we agreed.

---

## 1. Workflow (always in this order)

1. **Interview first.** Before drafting, ask focused questions about anything that would change the
   spec: problem, who uses the prediction, data sources, label definition, constraints (deadline,
   compute, data access), what the professor evaluates. Ask in batches of at most 5 questions.
   Do not draft a full spec from a one-line prompt.
2. **Draft the skeleton.** Create the file with the section headings from §3 and fill in only what
   is known. Unknowns go in as markers (see §2), never as invented content.
3. **Fill section by section.** For each design choice (target definition, split strategy, metric,
   model family, imbalance handling), present 2–3 options with trade-offs and a recommendation, then
   **wait for my call**. Record the decision in the Decision Log (§3.16).
4. **Review pass.** Before calling the spec done, run the checklist in §5 and report what fails.

If I say "just draft it", draft everything, but mark every choice you made as `[ASSUMPTION]` so I
can review them one by one.

## 2. Markers

Use these inline, exactly as written, so they're greppable:

- `[ASSUMPTION]` — something you inferred; I must confirm or reject it.
- `[OPEN QUESTION]` — something nobody knows yet; include who/what could answer it.
- `[DECISION NEEDED]` — a choice between options; link to the options you listed.
- `[VERIFY]` — a fact that must be checked against the data or a source: dataset size, class
  balance, column meaning, missing-value rates, library behavior, a benchmark or paper result.
  Never state data statistics from memory or guesswork — they come from profiling the data.

A spec is not "done" while any `[DECISION NEEDED]` remains.

## 3. Spec structure

Use this order. Skip a section only by writing `N/A — <reason>`, never by omitting it silently.

### 3.1 Summary
Three to five sentences: what is predicted, for whom, why it matters. A professor should get it
in 30 s.

### 3.2 Problem and context
The pain today, who feels it, how it's handled now, and why ML is the right tool.
**Challenge this section:** if descriptive statistics, a rule, or a simple regression answers the
question, say so. Also state whether the goal is **prediction** or **explanation/inference** —
they lead to different models and different evaluation.

### 3.3 Goals and non-goals
Bullet lists. Non-goals are mandatory — they are how we protect an academic deadline.

### 3.4 Users and decisions supported
Who consumes the output and what decision changes because of it. State the **cost of each error
type** (false positive vs false negative, over- vs under-estimate). This drives the metric choice
in §3.12.

### 3.5 Requirements
- Functional, numbered `FR-01`… (e.g. "the pipeline MUST produce predictions for a CSV with the
  schema in §3.8"). MUST / SHOULD / MAY. Each must be testable.
- Non-functional, numbered `NFR-01`…: compute budget and training time, inference latency if it
  matters, reproducibility, privacy and data protection (LGPD; ethics approval if human-subject or
  health data), maintainability.

### 3.6 ML problem formulation
- Task type (binary/multiclass classification, regression, clustering, time series…).
- **Target definition:** exact formula or rule that creates the label from raw data, with edge cases.
- Unit of prediction (one row = one patient? one visit? one day?).
- **Prediction time:** the moment the prediction is made, and therefore which information is
  available then. Everything after this moment is off-limits as a feature.
- Label source and quality: who/what produced it, known noise or delays.

### 3.7 Data
Sources, access and license, time period, row count, collection process, data dictionary (or link),
known biases and coverage gaps, missingness patterns, duplicates, and the data quality checks the
pipeline runs. Anonymization and storage rules for personal data. `[VERIFY]` every number via
profiling.

### 3.8 Splitting and leakage
- Split strategy and why it matches real use: random, stratified, **temporal**, or **grouped**
  (same entity never in both train and test).
- Train / validation / test sizes. The **test set is frozen** and used once, at the end.
- Leakage review: list every feature and confirm it is available at prediction time (§3.6) and
  isn't a proxy for the label. Preprocessing is fit on training data only.

### 3.9 Features and preprocessing
Feature list with origin, type, and transformation. Encoding, imputation, scaling, outlier handling,
feature selection. Class imbalance strategy (class weights, resampling, threshold tuning), applied
only inside training folds. All of it expressed as a single pipeline object, not ad-hoc steps.

### 3.10 Baselines
**Mandatory.** At least a trivial baseline (majority class / mean / last value) and a simple model
(e.g. logistic or linear regression). Every other model is judged against these.

### 3.11 Modeling
Candidate model families and why, hyperparameter search method and space, validation scheme
(k-fold, stratified, grouped, time-series CV), and the selection rule (which metric, on which data,
how ties are broken).

### 3.12 Evaluation plan
- Primary metric, justified by the error costs in §3.4 (e.g. recall or PR-AUC for rare positives,
  not accuracy). Secondary metrics.
- Decision threshold and how it's chosen (on validation, never on test).
- Calibration, if probabilities are used as risk scores.
- Uncertainty: confidence intervals (bootstrap or CV spread), not single numbers.
- Subgroup metrics (age, sex, region… whatever is relevant) to detect uneven performance.
- Error analysis plan: which mistakes will be inspected and how.
- Acceptance thresholds tied to FRs, stated relative to the baseline.

### 3.13 Interpretability and fairness
How results are explained (coefficients, feature importance, SHAP, partial dependence) and the
limits of each. Fairness concerns for the subgroups in §3.12. If the goal is explanation, state that
feature importance is association, not causation.

### 3.14 Reproducibility and experiment tracking
Fixed seeds, pinned environment (requirements/lock file), data version or snapshot hash, config
files instead of hard-coded values, and where experiments are logged (MLflow, a results table…).
Anyone must be able to rerun the final result from a clean checkout.

### 3.15 Deliverables and interfaces
What gets delivered: notebook, report, trained model artifact, CLI or API. Input/output schemas
with examples. Contracts only — no implementation code.

### 3.16 Decision log
Lightweight ADRs: `D-01 — <title> — <date>`: context, options considered, decision, consequences.

### 3.17 Risks
Table: risk, likelihood, impact, mitigation. Include insufficient or low-quality data, label noise,
leakage discovered late, class imbalance, compute limits, and deadline risk.

### 3.18 Milestones
Aligned with the academic calendar and deliverables. Typical order: data access and profiling →
baselines → modeling → final test evaluation → report. Each milestone lists the FRs it completes and
its exit criteria.

### 3.19 Academic deliverables mapping
Map each item the professor/rubric requires to the section of this spec that covers it.
`[OPEN QUESTION]` if I haven't shared the rubric yet — ask for it.

### 3.20 Open questions and glossary
Collect every `[OPEN QUESTION]` here. Glossary for domain terms and acronyms.

## 4. Writing rules

- Be concrete: numbers, examples, schemas. "Good accuracy" is not a requirement.
- One idea per bullet. Short sentences. No filler, no marketing tone.
- IDs (`FR-`, `NFR-`, `D-`) are stable — never renumber; deprecate with ~~strikethrough~~ instead.
- Cross-reference by ID (e.g. "satisfies FR-03, measured by the primary metric in §3.12").
- Do not invent stakeholders, data statistics, or professor requirements. Ask or mark them.
- Cite external sources (docs, papers, dataset documentation) with links when a claim depends on them.
- Language: write the spec in the language I use in the request. If the spec is an academic
  deliverable, ask whether it should be in Portuguese (pt-BR) before drafting.
- For large projects, split into `specs/00-overview.md` plus one file per component, and keep the
  overview as the index.

## 5. Done checklist

Before saying a spec is ready, check and report each line as pass/fail:

- [ ] Every FR and NFR is testable and has an ID.
- [ ] Target, unit of prediction, and prediction time are defined.
- [ ] Split strategy matches how the model would be used; test set is used once.
- [ ] Every feature passed the leakage review.
- [ ] Baselines are defined and acceptance thresholds are relative to them.
- [ ] Primary metric is justified by error costs; uncertainty will be reported.
- [ ] Subgroup evaluation is planned or marked `N/A — <reason>`.
- [ ] The final result is reproducible from seed, config, and data version.
- [ ] Non-goals are listed.
- [ ] No `[DECISION NEEDED]` left; remaining `[ASSUMPTION]`s are listed for me.
- [ ] Every `[VERIFY]` is either verified against the data/a dated source or listed as pending.
- [ ] Decision log has an entry for each significant choice.
- [ ] Milestones fit the academic deadline, with buffer.

## 6. How to work with me

- **I decide, you execute.** Never pick a target definition, split, metric, model, or scope cut
  silently.
- **Push back.** If a requirement is vague, the problem doesn't need ML, the data can't support the
  question, or the plan is over-engineered for an academic deadline, say so once, clearly, with
  reasons. Then follow my decision.
- **Teach briefly.** When a concept appears that I may not know (data leakage, grouped vs temporal
  splits, calibration, PR-AUC vs ROC-AUC under imbalance, SHAP limitations), explain the *why* in
  1–3 sentences.
- **End every session** with: what changed in the spec, decisions still pending, what you didn't
  verify.