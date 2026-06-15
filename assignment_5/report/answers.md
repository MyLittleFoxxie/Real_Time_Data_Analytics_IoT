# Assignment 5 — Answer-Box Content

**ENGR 5785G — Real-Time Data Analytics IoT** · Vitor Brandao Raposo (101011969) · 06/2026

Paste each block below into the matching answer box in the assignment PDF. For every code
modification the three required items are stated: **class → function → updated line(s)**.
All evidence (numbers, charts) is produced by `Raposo_Vitor_V2X_Sensitivity.ipynb`.

---

## Part A — Resource Profile Analysis

**Class:** `MultiAgentV2XOffloadEnv` **Function:** `step()` (`env.py`)

Routing is set by `act` inside the per-vehicle loop. Force the layer at the top of the loop —
one override line per profile makes every other tier unreachable regardless of the agent:

```python
# inside step(), first line of `for i in range(self.n):`
act = actions[i]

act = 0   # 1. EDGE-ONLY   : all tasks execute locally   (Fog + Cloud disabled)
act = 1   # 2. RSU/FOG-ONLY: all tasks offload to Fog     (Edge + Cloud disabled)
act = 2   # 3. CLOUD-ONLY  : all tasks offload to Cloud    (Edge + Fog disabled)
```

Each profile uses exactly one of the three `act = …` lines.

### Question A1
1. **Lowest average response time:** **Cloud-Only** among the three fixed profiles; the
   **Dynamic** policy (per-task best layer) is lowest overall.
2. **Why:** Edge-Only has no communication delay but is throttled by the weak on-board CPU
   (1.0–2.5 GHz), so the compute term `b·c_i/f_edge` dominates → highest latency. Fog-Only adds
   the uplink `b/r_v2i` but runs on 16 GHz, cutting latency sharply. Cloud-Only also pays the
   fixed 35 ms backhaul yet runs on 80 GHz; the compute saving outweighs the small constant
   backhaul, so it beats Fog. **When tasks are compute-heavy, computational capacity dominates
   communication overhead**, so offloading to stronger tiers wins.

---

## Part B — Number of RSUs

**Class:** `MultiAgentV2XOffloadEnv` **Function:** `__init__()` (`env.py`, line 24)

```python
# before:
self.rsu_positions = [250.0, 750.0]                  # 2 RSUs
# after (e.g. 4 RSUs evenly spaced on the 1000 m road):
self.rsu_positions = [125.0, 375.0, 625.0, 875.0]    # 4 RSUs
```

### Question B1
Yes — more RSUs reduce communication latency, with **diminishing returns**. The rate model
`r_v2i = clip(150 / (1 + 0.005·d_min²), 15, 150)` falls off with the **square** of the distance
to the nearest RSU. More RSUs shrink `d_min`, raising `r_v2i` and lowering the uplink term
`b/r_v2i`. Once RSUs are dense the rate saturates at its 150 MB/s clip and the (RSU-independent)
compute term becomes the floor. **Shorter distance ⇒ higher rate ⇒ lower latency, until distance
is no longer the bottleneck.**

---

## Part C — Data Size Analysis

**Class:** `MultiAgentV2XOffloadEnv` **Functions:** `reset()` (line 41) **and** `step()`
(line 91) — the size is sampled in **both**, so both lines change.

```python
# before:
self.data_sizes = np.random.uniform(0.5, 4.0, self.n)
# after:
self.data_sizes = np.random.uniform(1.0, 8.0, self.n)
```

### Question C1
Latency increases **~linearly** with task size `b`: the uplink `b/r_v2i` and the compute
`b·c_i/f` terms are both proportional to `b` (only the constant backhaul is not). Widening the
range to 1.0–8.0 MB raises mean response time by a comparable factor, widens the distribution,
and pushes more vehicles past the `τ_max` deadline.

---

## Part D — Edge CPU Frequency Analysis

**Class:** `MultiAgentV2XOffloadEnv` **Function:** `reset()` (`env.py`, line 42)

```python
# before:
self.f_edge = np.random.uniform(1.0, 2.5, self.n) * 1e9
# after:
self.f_edge = np.random.uniform(2.0, 4.0, self.n) * 1e9
```

### Question D1
Higher edge frequency lowers local latency because `t_edge = b·c_i/f_edge` is inversely
proportional to `f_edge` — raising 1.0–2.5 → 2.0–4.0 GHz roughly **halves** Edge-Only response
time (≈1.21 s → ≈0.67 s). **But under the dynamic optimal policy overall latency is essentially
unchanged** (≈0.192 s either way): even at 2–4 GHz the edge stays far slower than the Fog
(16 GHz) and Cloud (80 GHz) tiers for these task sizes, so the optimal router almost never picks
local execution. A stronger edge only pays off when local execution is actually used (small
tasks, or distant RSUs / congested links). It helps the edge path a lot but does not move the
system optimum here, because offloading already wins.

---

## Part E — Latency Component Analysis

**Class:** `MultiAgentV2XOffloadEnv` **Function:** `step()` (`env.py`, line 79, the
`elif act == 2:` cloud branch)

```python
# before:
t_exec = (b / self.r_v2i[i]) + self.d_backhaul + ((b * self.c_i) / self.f_cloud)
# after (communication delay only — backhaul and cloud-execution removed):
t_exec = (b / self.r_v2i[i])
```

Result: cloud response time collapses to just the transmission term; the measured difference
equals the backhaul (35 ms) plus the remote-compute contribution.

---

## Part F — Multi-Agent Backbone Change (add FITS)

Source: *"FITS: Modeling Time Series with 10k Parameters"* (ICLR 2024, repo `VEWOXIC/FITS`).
Core idea reproduced: a **complex-valued linear layer in the frequency domain** with reversible
instance norm — rFFT → low-pass cut → complex `nn.Linear` → irFFT → de-normalize.

**Class:** `DecentralizedAgent` **Function:** `__init__` — add branch:

```python
elif self.backbone_type == 'fits':
    self.input_dim = input_dim
    self.dominance_freq = input_dim // 2 + 1                      # number of rFFT bins (cut freq)
    self.freq_upsampler = nn.Linear(self.dominance_freq, self.dominance_freq, dtype=torch.cfloat)
    self.q_head = nn.Linear(input_dim, num_actions)
```

**Class:** `DecentralizedAgent` **Function:** `forward` — add branch:

```python
elif self.backbone_type == 'fits':
    x_mean = torch.mean(obs, dim=1, keepdim=True)
    x_var  = torch.var(obs, dim=1, keepdim=True) + 1e-5
    x = (obs - x_mean) / torch.sqrt(x_var)                        # RIN normalize
    low_specx = torch.fft.rfft(x, dim=1)                          # to frequency domain
    low_specx = low_specx[:, :self.dominance_freq]               # low-pass filter
    low_specxy = self.freq_upsampler(low_specx)                  # complex linear (FITS core)
    recon = torch.fft.irfft(low_specxy, n=self.input_dim, dim=1) # back to time domain
    recon = recon * torch.sqrt(x_var) + x_mean                   # de-normalize
    return self.q_head(recon), None
```

**Result:** FITS trains inside the QMIX pipeline and reaches reward comparable to
MLP/LSTM/Transformer while using far fewer parameters (only a small complex frequency layer +
linear Q-head) — matching FITS' compact-model claim, which suits resource-constrained on-vehicle
inference.
