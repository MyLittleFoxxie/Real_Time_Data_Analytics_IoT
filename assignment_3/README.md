# Module 3 Assignment — Feature Extraction & Feature Selection

Repository for Ontario Tech course **ENGR 5785G — Real-Time Data Analytics IoT**.

Student: Vitor Brandao Raposo

Student ID: 101011969

Date: 05/2026

---

## Quick Start (Windows)

```powershell
# 1. Activate the project virtual environment (from assignment_3/)
..\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the dataset from Kaggle and place it next to the notebook:
#    https://www.kaggle.com/datasets/mirichoi0218/insurance
#    → assignment_3/insurance.csv
#    (file is gitignored — do NOT commit or submit it)

# 4. Launch Jupyter
jupyter notebook LastName_FirstName_FeatureEng.ipynb
```

To execute the whole notebook from the command line (the grader's
"runs top-to-bottom without errors" check):

```powershell
jupyter nbconvert --to notebook --execute LastName_FirstName_FeatureEng.ipynb --output LastName_FirstName_FeatureEng.ipynb
```

---

## Repository Structure

```text
assignment_3/
├── Feature Engineering Assigment.pdf      ← Assignment spec (4 pages + rubric)
├── LastName_FirstName_FeatureEng.ipynb    ← The deliverable (rename before submitting → Raposo_Vitor_FeatureEng.ipynb)
├── insurance.csv                          ← Kaggle dataset (gitignored — NOT submitted)
├── requirements.txt                       ← Allowed libs only: pandas, numpy, scikit-learn, matplotlib, seaborn
├── .gitignore                             ← Keeps insurance.csv and ipynb checkpoints out of git
└── README.md                              ← This file
```

The notebook is organized to match the rubric one-to-one. Each Part is a
level-1 markdown heading; each sub-task is a level-2 heading with the exact
rubric label so the grader can locate it:

| Cells               | Rubric                                          | Points |
| ------------------- | ----------------------------------------------- | ------ |
| `# Cell 1`          | Imports + load + target + label encoding        | —      |
| `## A1`             | Data Loading & Inspection                       | 5      |
| `## A2`             | Univariate & Bivariate Analysis                 | 5      |
| `## B1.1`           | BMI Category (ordinal)                          | 4      |
| `## B1.2`           | Smoker × BMI interaction                        | 4      |
| `## B1.3`           | Age Group (ordinal)                             | 4      |
| `## B1.4`           | Family Risk Score (composite)                   | 4      |
| `## B1.5`           | Log Charges (log1p, before/after plot)          | 4      |
| `## B2`             | Original feature (chi² validated)               | 10     |
| `## C1`             | Filter — Pearson + SelectKBest(chi², k=6) + |r|>0.85 drop | 10 |
| `## C2`             | Embedded — Random Forest importances + bottom-5 | 10     |
| `## C3`             | Wrapper — RFE + Feature Selection Summary table | 10     |
| `## D1`             | Logistic Regression — Baseline / Extracted / Selected | 20 |
| `## D2 (bonus)`     | GradientBoostingClassifier on the same 3 splits | bonus  |
| `## E1`             | Results summary table + biggest-gain feature    | 4      |
| `## E2`             | Critical analysis (when extraction hurts)       | 4      |
| `## E3`             | Fairness/legal reflection                       | 2      |

---

## Dataset

Kaggle: <https://www.kaggle.com/datasets/mirichoi0218/insurance>

Expected schema (file must contain these 7 columns):

| Column     | Type   | Description                                        |
| ---------- | ------ | -------------------------------------------------- |
| `age`      | int    | Patient age in years (18–64)                       |
| `sex`      | string | `male` / `female`                                  |
| `bmi`      | float  | Body Mass Index — weight(kg) / height(m)²          |
| `children` | int    | Number of dependents covered                       |
| `smoker`   | string | `yes` / `no` — tobacco smoker                      |
| `region`   | string | `northeast` / `southeast` / `southwest` / `northwest` |
| `charges`  | float  | Annual medical cost billed — used to build target  |

Target (created in Cell 1):

```python
df['high_charges'] = (df['charges'] > df['charges'].median()).astype(int)
```

> **Submission rule:** the CSV is **gitignored** and **must not be submitted**.
> The grader will source it from Kaggle.

---

## Part A — Exploratory Data Analysis (10 pts)

Cells `## A1` and `## A2`.

- **A1.** `df.head(10)`, `df.dtypes`, `df.describe()`, missing-value count + %
  per column, class balance of `high_charges` via `value_counts()`.
- **A2.** Histogram + KDE of `charges` (note skew + modelling implication),
  boxplot of `bmi` grouped by `smoker`, grouped bar chart of mean `charges`
  by `region × sex`, correlation matrix heatmap of numeric variables.
  Closing markdown cell: 3–5 sentences naming two EDA findings that motivate
  the engineered features.

---

## Part B — Feature Extraction (30 pts)

Cells `## B1.1` … `## B2`. **Six new features total** (B1.1–B1.5 + B2). Every
feature cell contains three things: **(1)** the engineering code, **(2)** a
short markdown justification, **(3)** one plot or summary statistic showing
its relationship to `high_charges`.

| Cell    | Feature              | Definition                                                                 |
| ------- | -------------------- | -------------------------------------------------------------------------- |
| B1.1    | `bmi_category`       | Ordinal int: 0=Underweight (<18.5), 1=Normal (18.5–24.9), 2=Overweight (25–29.9), 3=Obese (≥30) |
| B1.2    | `smoker_bmi`         | `smoker_encoded × bmi` — multiplicative interaction                        |
| B1.3    | `age_group`          | Ordinal int: 0=Young Adult (18–35), 1=Middle-Aged (36–50), 2=Senior (51+)  |
| B1.4    | `family_risk`        | Composite of `children` and `age` (formula justified in cell)              |
| B1.5    | `log_charges`        | `np.log1p(charges)` — before/after distribution plot, statistical benefit  |
| B2      | (student's own)      | Justified + plotted + chi² validated against `high_charges`                |

> **Note on B1.5:** `log_charges` is created as a feature for distribution
> analysis; the binary target `high_charges` is still computed from raw
> `charges` (the median split is invariant under monotonic transformation,
> so this is consistent with the spec).

---

## Part C — Feature Selection (30 pts)

Cells `## C1`, `## C2`, `## C3`.

- **C1 — Filter.** Pearson correlation of all numeric features with
  `high_charges` (ranked bar chart by `|r|`), then
  `SelectKBest(chi2, k=6)` on non-negative features (report names + χ²
  scores), then drop any feature with `|r| > 0.85` against another feature
  (each drop justified inline).
- **C2 — Embedded.** `RandomForestClassifier(n_estimators=100, random_state=42)`
  on all features, horizontal-bar plot of `.feature_importances_`, top-5 list,
  then a second RF trained on **only the bottom-5** features — compare
  5-fold CV accuracy against the full-feature RF and interpret the gap.
- **C3 — Wrapper.** `RFE(LogisticRegression(max_iter=1000), n_features_to_select=6)`;
  report selected feature names.

**Required Feature Selection Summary table** (rendered as the closing markdown
cell of C3 — rows are features, columns are the four methods + your verdict):

| Feature | Correlation Rank | Chi² Selected | RF Importance Rank | RFE Selected | Your Verdict |
| ------- | ---------------- | ------------- | ------------------ | ------------ | ------------ |
| …       | …                | ✓ / ✗         | …                  | ✓ / ✗        | keep / drop  |

The verdict column locks in the **top-6 feature set** consumed by the
"Selected" experiment in Part D.

---

## Part D — Model Comparison (20 pts)

Cell `## D1`. Logistic Regression with
`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` and
`cross_val_score` reporting **Accuracy, F1, AUC-ROC** for three experiments:

| Experiment | Features                                                | Extra report           |
| ---------- | ------------------------------------------------------- | ---------------------- |
| Baseline   | `age, sex, bmi, children, smoker, region` (encoded only) | —                     |
| Extracted  | All original + all 6 engineered                          | —                     |
| Selected   | Top-6 from the Part C verdict column                     | **Confusion matrix** (via `cross_val_predict`) |

### Part D2 — Bonus

Cell `## D2 (bonus)`. Same three feature sets, swap the estimator to
`sklearn.ensemble.GradientBoostingClassifier(random_state=42)`. Closing
markdown cell answers in 3–5 sentences whether feature engineering still
helps once a tree-based booster is doing implicit interactions.

> XGBoost is **not** used — the PDF's library whitelist is
> pandas / numpy / scikit-learn / matplotlib / seaborn only, and sklearn's
> built-in `GradientBoostingClassifier` is the in-spec choice.

---

## Part E — Written Analysis & Reflection (10 pts)

Markdown-only cells.

- **E1 (4 pts).** Results table copying the D1 numbers + one paragraph
  identifying the single engineered feature that produced the biggest gain
  (cite either the C2 importance rank or the C1 correlation magnitude as
  evidence).
- **E2 (4 pts).** One case where engineering **hurt** performance (likely
  the Extracted run vs. Selected, due to multicollinearity / redundant
  encodings) + one feature that did not improve the model.
- **E3 (2 pts).** Fairness/legal reflection — call out the features you'd
  hesitate to deploy in a real insurance pricing context (`sex`, `region`,
  and any interaction that proxies them).

---

## Running Tests

There are no unit tests for this assignment — correctness is verified by
running the notebook end-to-end. The single grader-facing check is:

```powershell
jupyter nbconvert --to notebook --execute LastName_FirstName_FeatureEng.ipynb --output LastName_FirstName_FeatureEng.ipynb
```

Exit status `0` and no traceback cells = "runs top-to-bottom without errors".

---

## Submission Checklist (from PDF page 5)

Before submitting on Canvas, confirm:

- [ ] File renamed to **`Raposo_Vitor_FeatureEng.ipynb`** (LastName_FirstName format)
- [ ] Notebook runs top-to-bottom without errors (`jupyter nbconvert --execute` exits 0)
- [ ] `insurance.csv` is **NOT** in the submission (sourced from Kaggle by grader)
- [ ] Imports only `pandas`, `numpy`, `scikit-learn`, `matplotlib`, `seaborn` — no other packages
- [ ] All five parts (A, B, C, D, E) labelled with rubric headings
- [ ] At least 6 engineered features present (B1.1–B1.5 + B2)
- [ ] Feature Selection Summary table present in C3
- [ ] D1: three experiments reported with Accuracy / F1 / AUC-ROC; Selected has confusion matrix
- [ ] E1 / E2 / E3 written analyses are in markdown/comment cells (not code comments)
- [ ] Submission date noted — late policy is **–10% per day, max 5 days**

**Academic integrity:** Per the PDF, generative-AI tools may **not** be used
to write the analysis or code. This scaffold provides structure only — the
written analyses (A2 finding, B1/B2 justifications, C verdict column,
E1–E3) must be authored by the student from the data.
