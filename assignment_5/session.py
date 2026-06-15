# session.py
import pygame
import numpy as np
import matplotlib.pyplot as plt

class OffloadingSession:
    def __init__(self, env, visualizer, agent, max_timesteps=100):
        self.env = env
        self.vis = visualizer
        self.agent = agent
        self.max_steps = max_timesteps
        self.history_total_system_latency = []
        self.history_per_vehicle_latency = [[] for _ in range(self.env.n)]
        self.deadline_violations_count = 0

    def run(self):
        obs, info = self.env.reset()
        for step in range(self.max_steps):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.vis.close()
                    return
            
            # Polymorphic action selection
            actions = self.agent.compute_actions(obs)
            next_obs, reward, _, _, step_info = self.env.step(actions)
            latencies = step_info["latencies"]
            
            self.history_total_system_latency.append(sum(latencies))
            for i in range(self.env.n):
                self.history_per_vehicle_latency[i].append(latencies[i])
                if latencies[i] > self.env.tau_max:
                    self.deadline_violations_count += 1
            
            self.vis.render_frame(current_step=step, max_steps=self.max_steps)
            self.vis.update_live_plot()
            self.vis.clock.tick(15) 
            
        self.vis.close()
        self.display_summary_dashboard()

    def display_summary_dashboard(self):
        plt.ioff() 
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
        fig.suptitle("V2X Offloading Session Performance Analysis Summary", fontsize=14, fontweight='bold')

        ax1.plot(self.history_total_system_latency, color='#6366f1', linewidth=2, label="Cumulative Fleet Delay")
        ax1.set_title("Total Fleet Latency Over Time")
        ax1.set_xlabel("Session Step Index")
        ax1.set_ylabel("Total Latency (Seconds)")
        ax1.grid(True, linestyle=':', alpha=0.6)
        ax1.legend()

        avg_latencies = [np.mean(self.history_per_vehicle_latency[i]) for i in range(self.env.n)]
        bars = ax2.bar([f"AV {i+1}" for i in range(self.env.n)], avg_latencies, color='#10b981', edgecolor='black')
        ax2.axhline(y=self.env.tau_max, color='#ef4444', linestyle='--', linewidth=2, label="Safety Limit")
        ax2.set_title("Mean Processing Latency per Vehicle")
        ax2.set_ylabel("Time (Seconds)")
        ax2.set_ylim(0, max(max(avg_latencies)*1.3, self.env.tau_max * 1.2))
        ax2.legend()
        
        for bar in bars:
            height = bar.get_height()
            ax2.annotate(f'{height:.3f}s',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        
        print("\n" + "="*40)
        print("         SESSION STATISTICS REPORT       ")
        print("="*40)
        print(f"Total Session Duration   : {self.max_steps} tracking ticks")
        print(f"Mean Fleet Delay Metric  : {np.mean(self.history_total_system_latency):.4f} seconds")
        print(f"Total Deadline Failures  : {self.deadline_violations_count} failures observed")
        print(f"Safety Violation Rate    : {(self.deadline_violations_count / (self.max_steps * self.env.n)) * 100:.2f}%")
        print("="*40 + "\n")
        
        plt.show()

