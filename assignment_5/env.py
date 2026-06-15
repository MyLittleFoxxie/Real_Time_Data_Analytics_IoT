import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pygame
import matplotlib.pyplot as plt
import sys

# =====================================================================
# 1. THE RIGOROUS V2X ENVIRONMENT
# =====================================================================
class MultiAgentV2XOffloadEnv(gym.Env):
    def __init__(self, n_vehicles=4, tau_max=0.150):
        super(MultiAgentV2XOffloadEnv, self).__init__()
        self.n = n_vehicles
        self.tau_max = tau_max 
        
        # PROFILE 1: Balanced Dynamic Mode (Perfect Edge-Fog-Cloud separation)
        self.c_i = 8e8              # Task complexity: 100k CPU cycles per MB
        self.f_fog = 16.0 * 1e9    # Fog server capacity: 16 GHz
        self.f_cloud = 80.0 * 1e9  # Cloud capacity: 80 GHz
        self.d_backhaul = 0.035   # Cloud fiber transport delay: 35ms

        self.road_length = 1000.0 
        self.rsu_positions = [250.0, 750.0] 
        
        self.action_space = spaces.Tuple([spaces.Discrete(3) for _ in range(self.n)])
        self.observation_space = spaces.Tuple([
            spaces.Box(low=np.array([0.0, 0.0, 0.0, 0.0]), 
                       high=np.array([10.0, 5.0, 300.0, 1000.0]), 
                       dtype=np.float32) for _ in range(self.n)
        ])
        
        self.last_latencies = np.zeros(self.n)
        self.last_actions = np.zeros(self.n, dtype=int)
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.car_positions = np.linspace(50.0, 850.0, self.n)
        self.car_speeds = np.random.uniform(15.0, 30.0, self.n) 
        self.data_sizes = np.random.uniform(0.5, 4.0, self.n)     
        self.f_edge = np.random.uniform(1.0, 2.5, self.n) * 1e9   
        self.r_v2i = self._calculate_channel_rates()
        return self._get_all_obs(), {}

    def _calculate_channel_rates(self):
        rates = []
        for pos in self.car_positions:
            min_dist = min([abs(pos - rsu) for rsu in self.rsu_positions])
            base_rate = 150.0 
            rate = base_rate / (1.0 + 0.005 * (min_dist ** 2))
            rates.append(np.clip(rate, 15.0, 150.0))
        return np.array(rates)

    def _get_all_obs(self):
        obs_list = []
        for i in range(self.n):
            obs_list.append(np.array([
                self.data_sizes[i], 
                self.f_edge[i] / 1e9, 
                self.r_v2i[i] / 100.0,
                self.car_positions[i] / 1000.0
            ], dtype=np.float32))
        return obs_list

    def step(self, actions):
        individual_latencies = []
        self.last_actions = np.array(actions, dtype=int)
        
        for i in range(self.n):
            act = actions[i]
            b = self.data_sizes[i]
            
            if act == 0:    
                t_exec = (b * self.c_i) / self.f_edge[i]
            elif act == 1:  
                t_exec = (b / self.r_v2i[i]) + ((b * self.c_i) / self.f_fog)
            elif act == 2:  
                t_exec = (b / self.r_v2i[i]) + self.d_backhaul + ((b * self.c_i) / self.f_cloud)
                
            individual_latencies.append(t_exec)

        self.last_latencies = np.array(individual_latencies)
        total_system_latency = np.mean(individual_latencies)
        reward = -total_system_latency
        
        # Move cars forward
        self.car_positions += self.car_speeds * 0.1 
        self.car_positions = np.mod(self.car_positions, self.road_length)
        
        self.data_sizes = np.random.uniform(0.5, 4.0, self.n)
        self.r_v2i = self._calculate_channel_rates()
        
        return self._get_all_obs(), reward, False, False, {"latencies": self.last_latencies}


# =====================================================================
# 2. THE VISUALIZATION LAYER (FIXED & EXPANDED)
# =====================================================================
class V2XSystemVisualizer:
    def __init__(self, env, width=1000, height=350):
        self.env = env
        self.width = width
        self.height = height
        
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Multi-Tier V2X Dynamic Offloading Engine")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 14)
        self.font_hud = pygame.font.SysFont("Arial", 16, bold=True) # Clear bold HUD font
        
        self.COLOR_BG = (15, 23, 42)       
        self.COLOR_ROAD = (51, 65, 85)     
        self.COLOR_RSU = (6, 182, 212)     
        self.COLOR_CLOUD = (168, 85, 247)  
        self.ACTION_COLORS = {0: (234, 179, 8), 1: (6, 182, 212), 2: (168, 85, 247)}

        plt.ion() 
        self.fig, self.ax = plt.subplots(figsize=(5, 3))
        self.fig.canvas.manager.set_window_title("Real-Time Delay Step Monitor")
        self.bars = self.ax.bar([f"AV {i+1}" for i in range(self.env.n)], np.zeros(self.env.n), color='cyan')
        self.ax.axhline(y=self.env.tau_max, color='red', linestyle='--', label=r"$\tau_{\max}$ Limit")
        self.ax.set_ylabel("Latency (Seconds)")
        self.ax.set_ylim(0, 0.350)
        self.ax.legend(loc="upper right")
        plt.tight_layout()

    def render_frame(self, current_step, max_steps):
        """Draws the spatial scene with fixed car numbers and a countdown timer."""
        self.screen.fill(self.COLOR_BG)
        road_y = 150
        
        # --- 1. HUD Counter System ---
        remaining_steps = max_steps - current_step
        hud_text = f"Session Status: Running ({remaining_steps} steps remaining)"
        lbl_hud = self.font_hud.render(hud_text, True, (241, 245, 249))
        self.screen.blit(lbl_hud, (self.width - 320, 20))

        # 2. Draw Simulated Highway Segments
        pygame.draw.rect(self.screen, self.COLOR_ROAD, (0, road_y, self.width, 60))
        pygame.draw.line(self.screen, (255, 255, 255), (0, road_y+30), (self.width, road_y+30), 2) 

        # 3. Draw Roadside Units
        for rsu_pos in self.env.rsu_positions:
            x_pixel = int((rsu_pos / self.env.road_length) * self.width)
            pygame.draw.rect(self.screen, self.COLOR_RSU, (x_pixel-15, road_y-50, 30, 40), border_radius=4)
            pygame.draw.line(self.screen, (255, 255, 255), (x_pixel, road_y-10), (x_pixel, road_y), width=2)
            lbl_rsu = self.font.render("RSU", True, (255, 255, 255))
            self.screen.blit(lbl_rsu, (x_pixel-11, road_y-40))

        # 4. Draw Vehicle Layers and Fixed Numerical Labels
        for i in range(self.env.n):
            pos_x = int((self.env.car_positions[i] / self.env.road_length) * self.width)
            pos_y = road_y + 15 if i % 2 == 0 else road_y + 35 
            action = self.env.last_actions[i]
            
            # Draw the car bounding box core
            pygame.draw.rect(self.screen, self.ACTION_COLORS[action], (pos_x-20, pos_y-10, 40, 20), border_radius=5)
            
            # --- FIX: Re-inserted car identity strings directly over the boxes ---
            lbl_car = self.font.render(f"AV {i+1}", True, (15, 23, 42)) # Slate dark text for readability
            self.screen.blit(lbl_car, (pos_x - 13, pos_y - 8))

            if action == 1: 
                closest_rsu = self.env.rsu_positions[np.argmin([abs(self.env.car_positions[i] - r) for r in self.env.rsu_positions])]
                rsu_x = int((closest_rsu / self.env.road_length) * self.width)
                pygame.draw.line(self.screen, self.COLOR_RSU, (pos_x, pos_y), (rsu_x, road_y-10), width=1)
            elif action == 2: 
                pygame.draw.line(self.screen, self.COLOR_CLOUD, (pos_x, pos_y), (pos_x, 0), width=1)

        # Draw Contextual UI Legends
        legend_txt = "Routing Space:   [Yellow] = Local Edge Core   |   [Cyan] = RSU Fog Layer   |   [Purple] = Cloud Infrastructure"
        lbl_legend = self.font.render(legend_txt, True, (203, 213, 225))
        self.screen.blit(lbl_legend, (20, self.height - 40))

        pygame.display.flip()

    def update_live_plot(self):
        for rect, h in zip(self.bars, self.env.last_latencies):
            rect.set_height(h)
            rect.set_color('#ef4444' if h > self.env.tau_max else '#10b981')
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def close(self):
        pygame.quit()
        plt.close(self.fig)


# =====================================================================
# 4. RUNTIME ENTRY PIPELINE
# =====================================================================
if __name__ == "__main__":
    v2x_env = MultiAgentV2XOffloadEnv(n_vehicles=4)
    ui_visualizer = V2XSystemVisualizer(v2x_env)
    
    session = OffloadingSession(v2x_env, ui_visualizer, max_timesteps=120)
    session.run()