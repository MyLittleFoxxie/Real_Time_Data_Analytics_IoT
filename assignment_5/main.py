# main.py
from env import MultiAgentV2XOffloadEnv, V2XSystemVisualizer
from agents.milp_agent import CentralizedMILPAgent
from agents.random_agent import RandomOffloadingAgent
from agents.madrl_agent import TransformerQMIXAgent
from session import OffloadingSession

def main():
    # 1. Initialize environment parameters
    env = MultiAgentV2XOffloadEnv(n_vehicles=2, tau_max=0.150)
    visualizer = V2XSystemVisualizer(env)
    
    # 2. Select decision architecture 
    # Easily swap this out later for: agent = TransformerQMIXAgent(env)
    #agent = RandomOffloadingAgent(env)  # Baseline uncoordinated agent
    agent = CentralizedMILPAgent(env)  # Optimal centralized agent (for benchmarking
        
    # 3. Instantiate and run the session pipeline
    session = OffloadingSession(env, visualizer, agent, max_timesteps=120)
    session.run()




# main.py
import torch
import numpy as np
import matplotlib.pyplot as plt
from env import MultiAgentV2XOffloadEnv, V2XSystemVisualizer
from session import OffloadingSession
from agents.madrl_agent import TransformerQMIXAgent
from buffer import MultiAgentReplayBuffer  # Assumes simple list/deque buffer implementation

def main_with_training():
    # 1. SETUP SHARED SYSTEM PARAMS
    chosen_backbone = 'transformer'
    max_episodes = 50
    max_steps = 200
    batch_size = 32
    
    env = MultiAgentV2XOffloadEnv(n_vehicles=4, tau_max=0.200)
    agent = TransformerQMIXAgent(env, backbone_type=chosen_backbone, epsilon=1.0)
    buffer = MultiAgentReplayBuffer(capacity=10000)
    
    reward_history = []
    print(f"--> Starting Headless Optimization Phase ({chosen_backbone.upper()}) <--")
    
    # 2. RUN HEADLESS TRAINING LOOP
    for ep in range(max_episodes):
        obs, info = env.reset()
        agent.reset_eval_memory()
        ep_reward = 0
        
        for step in range(max_steps):
            actions = agent.compute_actions(obs)
            next_obs, reward, terminated, truncated, _ = env.step(actions)
            buffer.push(obs, actions, reward, next_obs, terminated)
            
            obs = next_obs
            ep_reward += reward
            
            if len(buffer) > batch_size:
                b_obs, b_act, b_rew, b_n_obs, b_term = buffer.sample(batch_size)
                agent.train_step(b_obs, b_act, b_rew, b_n_obs, b_term)
                
            if terminated or truncated:
                break
                
        reward_history.append(ep_reward)
        if ep % 20 == 0:
            print(f"Episode {ep:03d}/{max_episodes} | Fleet Utility Reward: {ep_reward:.2f} | Epsilon: {agent.epsilon:.3f}")

    # 3. GENERATE OPTIMIZATION PERFORMANCE GRAPH
    print("--> Plotting Learning/Optimization Curve... <--")
    plt.figure(figsize=(8, 4))
    plt.plot(reward_history, label='QMIX Cumulative Reward', color='purple')
    plt.axhline(y=0, color='r', linestyle='--', label='Deadline Violation Baseline')
    plt.title(f'MADRL Resource Allocation Optimization Curve ({chosen_backbone.upper()})')
    plt.xlabel('Training Episodes')
    plt.ylabel('System Objective Score')
    plt.legend()
    plt.grid(True)
    plt.show(block=True) # Pauses loop until user reviews and closes window

    # 4. TRANSITION TO ACTIVE TESTING & DEPLOYMENT PHASE
    print("--> Commencing Visual System Testing Loop <--")
    agent.epsilon = 0.0  # Lock policy exploration (Strict Greedy Inference)
    agent.reset_eval_memory()
    
    # Reinitialize a clean environment hooked into the Pygame graphic renderer
    test_env = MultiAgentV2XOffloadEnv(n_vehicles=4, tau_max=0.200)
    visualizer = V2XSystemVisualizer(test_env)
    
    session = OffloadingSession(test_env, visualizer, agent, max_timesteps=120)
    session.run()

if __name__ == "__main__":
    main()
    #main_with_training()