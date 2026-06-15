# agents/random_agent.py
import numpy as np
from interfaces import BaseOffloadingAgent

class RandomOffloadingAgent(BaseOffloadingAgent):
    """
    A baseline tracking agent that makes purely random offloading decisions.
    Used as an uncoordinated lower-bound reference benchmark for students.
    """
    def __init__(self, env):
        self.env = env
        
    def compute_actions(self, observations):
        """
        Ignores current observations and rolls an independent 3-sided die 
        (0=Edge, 1=Fog, 2=Cloud) for each vehicle agent.
        """
        # Returns an array of integers representing the randomly chosen layers
        random_actions = [np.random.choice([0, 1, 2]) for _ in range(self.env.n)]
        return random_actions