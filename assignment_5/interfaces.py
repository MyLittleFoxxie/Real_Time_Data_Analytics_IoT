# interfaces.py
class BaseOffloadingAgent:
    """Abstract interface for all offloading policies."""
    def compute_actions(self, observations):
        """Accepts a tuple of gym observations and returns a list of actions."""
        raise NotImplementedError