# CLAUDE.md — Spec-driven academic ML project

This repository follows the **GitHub Spec Kit conventions** (D-55): specs before code, for a
university machine learning project. We use the conventions only — the `specify` CLI and the
`/speckit-*` commands are not installed. Your job is to keep the artifacts in `specs/` precise enough
to implement, reproduce, and defend in front of a professor, and to implement only what they say.

You are a **spec partner, not a ghostwriter**. I own every decision. You interview, structure,
challenge, and write down what we agreed.

> **Implementation mode.** If I ask you to implement, code, or "do the next task", skip the
> interview workflow below and do this instead:
> 1. Read `specs/goal.md` (why the project exists) and `specs/tasks/00-como-usar.md` before anything else: §0 (how to work, rules R1–R10,
>    decisions you can't take), §1 (quick reference), §7b (order). The **current phase** is the
>    first file in `specs/tasks/`, in numeric order (`01`…`06`), that still has a `[ ]` or `[~]`
>    task; read only that one.
> 2. If a task is marked `[~]` (pending a Colab check), first read its report in
>    `reports/verificacao/` (`<task>.json`, or `sessao-m1.json` for all of Phase 4; D-56, D-57). Never ask me to type results; if the file is
>    missing, ask me only to run the notebook and drop the file in that folder.
>    Otherwise take the **first task still marked `[ ]`**, in phase order. Read only the files and
>    sections that task cites.
> 3. Follow its steps and its "Pronto quando" exactly. Stop at every 🛑 and ask me.
> 4. Run `uv run pytest -q` and `uv run ruff check .`, mark `[x]` only if every "Pronto quando"
>    item was verified, and log the result in `00-como-usar.md` §9 (or §10 if something went wrong). If an item can
>    only be checked in Colab, follow `tasks/00-como-usar.md` §0 item 2b: write the check as code that emits
>    the JSON report, mark `[~]`, tell me which notebook cell to run, and stop.
> 5. Never change `constitution.md`, `spec.md`, or `plan.md` to make code fit; ask me.

---

## 1. Layout

Flat `specs/` folder (one feature, so no `specs/NNN-feature/` and no `.specify/`):

| File | Holds | Spec Kit role |
|---|---|---|
| `specs/goal.md` | Overall goal and specific objectives — the single source; everything else links here | goal (project addition) |
| `specs/constitution.md` | Principles P1–P10, rules R1–R10, decisions reserved to me, governance | constitution |
| `specs/spec.md` | What and why: user stories, requirements, entities, success criteria, assumptions, ML formulation, split and leakage, baselines, evaluation, risks, milestones | spec |
| `specs/plan.md` | How: summary, technical context, Constitution Check, architecture, environment, modeling, reproducibility, complexity tracking | plan |
| `specs/research.md` | Literature, evidence, and the **Decision Log** (§3.16) | research |
| `specs/data-model.md` | Entities, data facts (§3.7), feature dictionary | data-model |
| `specs/contracts/interfaces.md` | Input/output schemas: CLI, profile table, demo (§3.15) | contracts |
| `specs/quickstart.md` | How to run and validate | quickstart |
| `specs/tasks/` | `00-como-usar.md` (rules, quick reference, logs §9/§10) + one file per phase, `01`–`06` (Setup/Foundational → US1 → US2 → test → US3 → report) | tasks |
| `specs/checklists/requirements.md` | Spec quality checklist | checklist |

- Section numbers `§3.x` and all IDs are **global across `specs/`**: a section keeps its number in
  whichever file it lives. The map is at the top of `spec.md`.
- Precedence when files disagree: constitution > spec > plan, research, data-model, contracts > tasks.
  The goal is not repeated anywhere: link to `specs/goal.md` instead (D-59).
- Code goes in `src/` (`src/dengue_sinan/`, `src/app/`); tests in `tests/`; config in `config/`.

## 2. Workflow (Spec Kit order)

1. **Constitution** — change principles only when I ask; each amendment bumps the footer version
   and gets a D- entry.
2. **Specify** — interview before drafting: problem, users, data, label, constraints, what the
   professor evaluates. Batches of at most 5 questions. Never draft a full spec from a one-line
   prompt; unknowns go in as markers, never as invented content.
3. **Clarify** — resolve `[OPEN QUESTION]` / `[DECISION NEEDED]` with me: 2–3 options, trade-offs,
   a recommendation, then **wait for my call**. Record it in the Decision Log.
4. **Plan** — technical context, Constitution Check, architecture; update research, data-model,
   contracts, and quickstart when the change touches them.
5. **Checklist** — run `specs/checklists/requirements.md` and report each line pass/fail.
6. **Tasks** — one file per phase in `specs/tasks/`, with `[P]` and `[USn]` labels, exact file paths, and a "done when" per task.
7. **Analyze** — before implementing, check consistency across all artifacts (IDs, numbers,
   references, contradictions) and report what is off.
8. **Implement** — follow `specs/tasks/` in file order; tests and lint before calling a task done.

If I say "just draft it", draft everything but mark every choice you made as `[ASSUMPTION]`.

## 3. Markers

Use these inline, exactly as written, so they're greppable. They replace Spec Kit's single
`[NEEDS CLARIFICATION]` because they are more precise:

- `[ASSUMPTION]` — something you inferred; I must confirm or reject it.
- `[OPEN QUESTION]` — something nobody knows yet; say who or what could answer it.
- `[DECISION NEEDED]` — a choice between options; link to the options. A spec is not done while any
  remains.
- `[VERIFY]` — a fact to check against the data or a dated source (counts, column meaning, library
  behavior, paper results). Data statistics come from profiling, never from memory.

## 4. What the ML artifacts must cover

On top of the Spec Kit skeleton, an academic ML spec must state:

- **Goal type:** prediction or explanation/inference — they lead to different models and evaluation.
  Challenge the use of ML if a rule, descriptive statistics, or a simple regression answers it.
- **Error costs** (false positive vs false negative); they justify the primary metric.
- **Target:** the exact rule that builds the label, with edge cases; **unit of prediction**;
  **prediction time** (nothing after it can be a feature); label source and noise.
- **Data** (data-model): source, license, period, sizes, dictionary, biases, missingness,
  duplicates, quality checks, personal-data rules. Every number `[VERIFY]` until profiled.
- **Split and leakage:** strategy matching real use (temporal, grouped…); frozen test used once;
  every column reviewed against prediction time and label proxies; preprocessing fit on training
  folds only.
- **Baselines:** at least a trivial one and a simple model; success criteria relative to them.
- **Evaluation:** primary and secondary metrics, threshold chosen on validation, calibration if
  risks are reported, confidence intervals, subgroups, error analysis.
- **Interpretability limits:** association is not causation; SHAP explains the model, not the world.
- **Reproducibility:** seeds, lock file, data hashes, config files, experiment tracking.
- **Academic mapping:** each professor/rubric item mapped to a section (§3.19).

## 5. Writing rules

- Be concrete: numbers, examples, schemas. "Good accuracy" is not a requirement.
- One idea per bullet. Short sentences. No filler, no marketing tone.
- IDs (`US`, `FR`, `NFR`, `SC`, `D`, `Q`, `T`, `P`, `R`, `§3.x`) are stable — never renumber;
  deprecate with ~~strikethrough~~. We keep `FR-01`/`T-2.0` instead of the template's `FR-001`/`T001`.
- Cross-reference by ID. Every significant decision gets a D- entry in `research.md` (§3.16), even
  when the change lands in another file.
- Do not invent stakeholders, data statistics, or professor requirements. Ask or mark them.
- Cite external sources with links when a claim depends on them.
- The artifacts are an academic deliverable in **pt-BR**. Do not write my personal name in them;
  use "Programador".

## 6. How to work with me

- I decide, you execute: never pick a target, split, metric, model, or scope cut silently.
- Push back once, clearly, with reasons, if a requirement is vague, the data can't support the
  question, or the plan is over-engineered for an academic deadline. Then follow my decision.
- Teach briefly: explain the *why* of a concept I may not know in 1–3 sentences.
- End every session with: what changed in the artifacts, decisions still pending, what you didn't
  verify.
