# buffer.py
import random
import numpy as np

class MultiAgentReplayBuffer:
    """
    A simple memory buffer that stores experiences across episodes
    so the QMIX agent can sample random batches for training.
    """
    def __init__(self, capacity=10000):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, obs, action, reward, next_obs, terminated):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (obs, action, reward, next_obs, terminated)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        # Unpack the batch into separate arrays
        obs, action, reward, next_obs, terminated = zip(*batch)
        return obs, action, reward, next_obs, terminated

    def __len__(self):
        return len(self.buffer)