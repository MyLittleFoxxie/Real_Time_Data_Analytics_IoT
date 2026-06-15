import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import copy  # Required for clean parameter deep-copying
from interfaces import BaseOffloadingAgent

class DecentralizedAgent(nn.Module):
    def __init__(self, input_dim=4, num_actions=3, hidden_dim=64, backbone_type='transformer'):
        super(DecentralizedAgent, self).__init__()
        self.backbone_type = backbone_type.lower()
        self.hidden_dim = hidden_dim
        
        if self.backbone_type == 'mlp':
            self.backbone = nn.Sequential(
                nn.Linear(input_dim, hidden_dim), nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim), nn.ReLU(),
                nn.Linear(hidden_dim, num_actions)
            )
        elif self.backbone_type == 'lstm':
            self.fc1 = nn.Linear(input_dim, hidden_dim)
            self.lstm = nn.LSTMCell(hidden_dim, hidden_dim)
            self.fc2 = nn.Linear(hidden_dim, num_actions)
        elif self.backbone_type == 'transformer':
            self.encoder = nn.Linear(input_dim, hidden_dim)
            layer = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=2, dim_feedforward=hidden_dim*2, batch_first=True)
            self.transformer = nn.TransformerEncoder(layer, num_layers=1)
            self.q_head = nn.Linear(hidden_dim, num_actions)
        elif self.backbone_type == 'fits':
            # FITS backbone ("Modeling Time Series with 10k Parameters", ICLR 2024).
            # The observation's `input_dim` features are treated as a length-`input_dim`
            # series. Core idea: rFFT -> low-pass cut -> COMPLEX linear layer in the
            # frequency domain -> irFFT, wrapped in reversible instance norm (RIN).
            self.input_dim = input_dim
            self.dominance_freq = input_dim // 2 + 1                       # number of rFFT bins (cut frequency)
            self.freq_upsampler = nn.Linear(self.dominance_freq, self.dominance_freq, dtype=torch.cfloat)  # complex linear
            self.q_head = nn.Linear(input_dim, num_actions)

    def forward(self, obs, hidden_state=None):
        if self.backbone_type == 'mlp':
            return self.backbone(obs), None
        elif self.backbone_type == 'lstm':
            h, c = (torch.zeros(obs.size(0), self.hidden_dim, device=obs.device), torch.zeros(obs.size(0), self.hidden_dim, device=obs.device)) if hidden_state is None else hidden_state
            h, c = self.lstm(F.relu(self.fc1(obs)), (h, c))
            return self.fc2(h), (h, c)
        elif self.backbone_type == 'transformer':
            x = obs.unsqueeze(1) if len(obs.shape) == 2 else obs
            return self.q_head(self.transformer(F.relu(self.encoder(x))).squeeze(1)), None
        elif self.backbone_type == 'fits':
            # Reversible instance norm (RIN): standardize across the feature/"time" axis.
            x_mean = torch.mean(obs, dim=1, keepdim=True)
            x_var = torch.var(obs, dim=1, keepdim=True) + 1e-5
            x = (obs - x_mean) / torch.sqrt(x_var)
            low_specx = torch.fft.rfft(x, dim=1)                 # to frequency domain (complex)
            low_specx = low_specx[:, :self.dominance_freq]       # low-pass filter (keep dominant freqs)
            low_specxy = self.freq_upsampler(low_specx)          # FITS core: complex linear in freq domain
            recon = torch.fft.irfft(low_specxy, n=self.input_dim, dim=1)  # back to time domain
            recon = recon * torch.sqrt(x_var) + x_mean           # de-normalize (RIN inverse)
            return self.q_head(recon), None

class QMIXMixer(nn.Module):
    def __init__(self, n_agents=4, state_dim=16, mix_hidden_dim=32):
        super(QMIXMixer, self).__init__()
        self.n_agents, self.mix_hidden_dim = n_agents, mix_hidden_dim
        self.hyper_w1 = nn.Sequential(nn.Linear(state_dim, mix_hidden_dim), nn.ReLU(), nn.Linear(mix_hidden_dim, n_agents * mix_hidden_dim))
        self.hyper_w2 = nn.Sequential(nn.Linear(state_dim, mix_hidden_dim), nn.ReLU(), nn.Linear(mix_hidden_dim, mix_hidden_dim))
        self.hyper_b1 = nn.Linear(state_dim, mix_hidden_dim)
        self.hyper_b2 = nn.Sequential(nn.Linear(state_dim, mix_hidden_dim), nn.ReLU(), nn.Linear(mix_hidden_dim, 1))

    def forward(self, agent_qs, global_state):
        bs = agent_qs.size(0)
        w1 = torch.abs(self.hyper_w1(global_state)).view(bs, self.n_agents, self.mix_hidden_dim)
        w2 = torch.abs(self.hyper_w2(global_state)).view(bs, self.mix_hidden_dim, 1)
        hidden = F.elu(torch.bmm(agent_qs.unsqueeze(1), w1) + self.hyper_b1(global_state).view(bs, 1, self.mix_hidden_dim))
        return (torch.bmm(hidden, w2) + self.hyper_b2(global_state).view(bs, 1, 1)).view(bs, 1)

class TransformerQMIXAgent(BaseOffloadingAgent):
    def __init__(self, env, backbone_type='transformer', lr=1e-3, gamma=0.99, epsilon=1.0):
        self.env, self.n, self.gamma, self.epsilon = env, env.n, gamma, epsilon
        self.epsilon_min, self.epsilon_decay, self.obs_dim = 0.05, 0.992, 4
        self.state_dim, self.hidden_dim = self.n * self.obs_dim, 64
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"--> MADRL Allocation Agent initialized on device: {self.device} <--")
        
        # ACTIVE EVALUATION NETWORKS
        self.agents = nn.ModuleList([DecentralizedAgent(self.obs_dim, 3, self.hidden_dim, backbone_type).to(self.device) for _ in range(self.n)])
        self.mixer = QMIXMixer(self.n, self.state_dim, mix_hidden_dim=32).to(self.device)
        
        # FIX 1: STABLE TARGET NETWORKS (Cloned parameters to fix moving target issue)
        self.target_agents = copy.deepcopy(self.agents).to(self.device)
        self.target_mixer = copy.deepcopy(self.mixer).to(self.device)
        
        self.optimizer = torch.optim.Adam(list(self.agents.parameters()) + list(self.mixer.parameters()), lr=lr)
        self.eval_hidden_states = [None] * self.n
        self.train_step_count = 0

    def compute_actions(self, observations):
        actions = []
        with torch.no_grad():
            for i in range(self.n):
                if np.random.rand() < self.epsilon:
                    actions.append(np.random.choice([0, 1, 2]))
                else:
                    obs_tensor = torch.tensor(np.array(observations[i]), dtype=torch.float32, device=self.device).unsqueeze(0)
                    q, next_h = self.agents[i](obs_tensor, self.eval_hidden_states[i])
                    if next_h is not None: self.eval_hidden_states[i] = next_h
                    actions.append(torch.argmax(q).item())
        return actions

    def reset_eval_memory(self):
        self.eval_hidden_states = [None] * self.n

    def update_targets(self):
        """Hard parameters synchronization function."""
        self.target_agents.load_state_dict(self.agents.state_dict())
        self.target_mixer.load_state_dict(self.mixer.state_dict())

    def train_step(self, batch_obs, batch_actions, batch_rewards, batch_next_obs, batch_terminated):
        bs = len(batch_rewards)
        self.train_step_count += 1
        
        # FIX 2: PRE-CONVERT WHOLE BATCHES TO FIXED NUMPY ARRAYS FIRST (Prevents object tensor bugs)
        batch_obs_np = np.array(batch_obs, dtype=np.float32)
        batch_next_obs_np = np.array(batch_next_obs, dtype=np.float32)
        
        rewards_t = torch.tensor(batch_rewards, dtype=torch.float32, device=self.device).view(-1, 1)
        terminated_t = torch.tensor(batch_terminated, dtype=torch.float32, device=self.device).view(-1, 1)
        states_t = torch.tensor(batch_obs_np.reshape(bs, -1), dtype=torch.float32, device=self.device)
        next_states_t = torch.tensor(batch_next_obs_np.reshape(bs, -1), dtype=torch.float32, device=self.device)
        
        current_agent_qs, next_agent_max_qs = [], []
        for i in range(self.n):
            obs_i = torch.tensor(batch_obs_np[:, i, :], dtype=torch.float32, device=self.device)
            next_obs_i = torch.tensor(batch_next_obs_np[:, i, :], dtype=torch.float32, device=self.device)
            
            # Action selection uses active networks
            q_vals, _ = self.agents[i](obs_i)
            action_indices = torch.tensor([b[i] for b in batch_actions], dtype=torch.long, device=self.device).view(-1, 1)
            current_agent_qs.append(q_vals.gather(1, action_indices))
            
            # FIX 3: TARGET CALCULATIONS VIA TARGET NETWORKS ONLY
            next_q_vals, _ = self.target_agents[i](next_obs_i)
            next_agent_max_qs.append(next_q_vals.max(dim=1)[0].view(-1, 1))
            
        q_tot = self.mixer(torch.cat(current_agent_qs, dim=1), states_t)
        
        # Fully detach lookahead steps to prevent graph leaks
        next_q_tot = self.target_mixer(torch.cat(next_agent_max_qs, dim=1), next_states_t).detach()
        
        loss = F.mse_loss(q_tot, rewards_t + (self.gamma * next_q_tot * (1 - terminated_t)))
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        # Synchronize target networks every 100 gradient steps
        if self.train_step_count % 100 == 0:
            self.update_targets()
        
        if self.epsilon > self.epsilon_min: 
            self.epsilon *= self.epsilon_decay
            
        return loss.item()