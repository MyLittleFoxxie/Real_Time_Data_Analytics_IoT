# Module 5 Assignment — Sensitivity Analysis of a V2X Offloading Environment

Repository for Ontario Tech course **ENGR 5785G — Real-Time Data Analytics IoT**.

Student: Vitor Brandao Raposo · Student ID: 101011969 · Date: 06/2026

---

## What this is

The course provides a working **V2X multi-agent DRL offloading simulator** (`env.py`, `agents/`,
`session.py`, `buffer.py`, `main.py`). This assignment **modifies** it to study how networking
and compute parameters affect response time (Parts A–E) and **adds a new FITS backbone** to the
multi-agent QMIX agent (Part F).

The official submission is the assignment PDF with its answer boxes filled in. The answer-box
content is in [report/answers.md](report/answers.md). All claims are **validated** by running
[Raposo_Vitor_V2X_Sensitivity.ipynb](Raposo_Vitor_V2X_Sensitivity.ipynb), which reproduces each
modification live and measures its effect.

---

## Quick Start (Windows)

```powershell
# from assignment_5/
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# run the validation notebook end-to-end (grader's reproducibility check)
python -m nbconvert --to notebook --execute Raposo_Vitor_V2X_Sensitivity.ipynb `
  --output Raposo_Vitor_V2X_Sensitivity.ipynb --ExecutePreprocessor.timeout=900
```

> Note: this project's `.venv` is created by **uv**, whose `jupyter.exe` console-script
> trampoline fails on this machine. Invoke Jupyter tooling as a **module** (`python -m nbconvert`,
> `python -m jupyter notebook`) rather than the `jupyter` launcher. The notebook is executed with
> a registered kernel: `python -m ipykernel install --user --name a5venv`.

Runtime is a few minutes (Part F trains four backbones on CPU).

---

## Repository structure

```text
assignment_5/
├── Edge Intelligence V2X-multiagent-2.pdf      ← assignment spec (the deliverable to fill in)
├── Raposo_Vitor_V2X_Sensitivity.ipynb          ← validation notebook (Parts A–F)
├── report/
│   └── answers.md                              ← answer-box content for the PDF
├── env.py            ← V2X environment (read-only reference; Parts A–E edits documented, not applied)
├── agents/
│   ├── madrl_agent.py ← QMIX agent; FITS backbone ADDED here (Part F)
│   ├── milp_agent.py  ← optimal centralized baseline (used as "dynamic" policy)
│   └── random_agent.py
├── session.py, buffer.py, main.py              ← provided runtime (pygame path not used headless)
├── figures/                                    ← charts saved by the notebook
├── requirements.txt
└── README.md
```

---

## Mapping to the assignment

| Part | Topic | Where (class → function) | Notebook section |
| ---- | ----- | ------------------------ | ---------------- |
| A | Edge/Fog/Cloud-only profiles | `MultiAgentV2XOffloadEnv.step()` | Part A + Q A1 |
| B | Number of RSUs | `MultiAgentV2XOffloadEnv.__init__()` | Part B + Q B1 |
| C | Task size 0.5–4.0 → 1.0–8.0 MB | `reset()` **and** `step()` | Part C + Q C1 |
| D | Edge CPU freq 1.0–2.5 → 2.0–4.0 GHz | `reset()` | Part D + Q D1 |
| E | Cloud latency → comm-only | `step()` cloud branch | Part E |
| F | Add FITS backbone | `DecentralizedAgent.__init__` + `forward` | Part F |

Parts A–E are validated through a `ConfigurableV2XEnv` subclass in the notebook (one knob per
Part) so the original `env.py` stays pristine; the exact one-line edits for each answer box are
shown in the corresponding markdown cell and in `report/answers.md`. **Part F is applied for real**
in `agents/madrl_agent.py`, so `TransformerQMIXAgent(env, backbone_type='fits')` works end-to-end.

---

## Part F — FITS backbone

Based on *"FITS: Modeling Time Series with 10k Parameters"* (ICLR 2024, repo `VEWOXIC/FITS`).
The defining operation — a **complex-valued linear layer in the frequency domain** with
reversible instance normalization (rFFT → low-pass cut → complex `nn.Linear` → irFFT →
de-normalize) — is added as a `'fits'` branch alongside the existing `mlp`/`lstm`/`transformer`
backbones. It returns `(q_values, None)` like the others, so it drops into the QMIX training loop
unchanged and trains to reward levels comparable to the heavier backbones with a fraction of the
parameters.
