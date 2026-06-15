# agents/milp_agent.py
import numpy as np
from scipy.optimize import LinearConstraint, Bounds, milp
from interfaces import BaseOffloadingAgent

class CentralizedMILPAgent(BaseOffloadingAgent):
    def __init__(self, env):
        self.env = env
        
    def compute_actions(self, observations):
        """
        Calculates the mathematically optimal task offloading locations for the 
        entire fleet for this specific timestep using a centralized MILP solver.
        """
        N = self.env.n
        num_vars = 3 * N  # Each car has 3 possible choices (Edge, Fog, Cloud)
        c = []
        
        # ---------------------------------------------------------------------
        # 1. SETUP THE COST VECTOR (The Objective Function)
        # Here we calculate the latency cost for every possible choice per vehicle.
        # This maps straight to Equation (10) / \eqref{eq:ieee_objective} in the paper.
        # ---------------------------------------------------------------------
        for i in range(N):
            # Grab the current environment states for vehicle i
            b = self.env.data_sizes[i]   # Task payload size in MB
            f_e = self.env.f_edge[i]     # Onboard CPU frequency
            r_v = self.env.r_v2i[i]       # Dynamic uplink transmission speed
            
            # Choice 1: Keep it on the car (Local Edge) - Paper Eq (3)
            t_edge = (b * self.env.c_i) / f_e
            
            # Choice 2: Ship it to the nearest roadside server (Fog) - Paper Eq (4)
            t_fog = (b / r_v) + ((b * self.env.c_i) / self.env.f_fog)
            
            # Choice 3: Route it through the backhaul to the data center (Cloud) - Paper Eq (5)
            t_cloud = (b / r_v) + self.env.d_backhaul + ((b * self.env.c_i) / self.env.f_cloud)
            
            # Append these back-to-back. The solver expects a flat 1D list of costs:
            # [car1_edge, car1_fog, car1_cloud, car2_edge, car2_fog, ...]
            c.extend([t_edge, t_fog, t_cloud])
            
        # ---------------------------------------------------------------------
        # 2. SETUP THE ASSIGNMENT CONSTRAINTS 
        # We must force each car to pick EXACTLY ONE target layer. Tasks cannot be split.
        # This builds the constraint matrix for \eqref{con:ieee_exclusivity}.
        # ---------------------------------------------------------------------
        A_eq = np.zeros((N, num_vars))
        for i in range(N):
            # For each car's block of 3 choices, set coefficients to 1.0
            A_eq[i, i*3 : i*3 + 3] = 1.0
            
        # LinearConstraint(..., lb=1, ub=1) sets up the strict equality: LHS = 1
        constraints = LinearConstraint(A_eq, lb=np.ones(N), ub=np.ones(N))
        
        # ---------------------------------------------------------------------
        # 3. DEFINE DOMAINS (Binary Restrictions)
        # We can't have a car offloading 40% to Fog and 60% to Cloud. It's all-or-nothing.
        # This enforces the x_{i,k} \in {0, 1} constraint from \eqref{con:ieee_binary}.
        # ---------------------------------------------------------------------
        # An integrality array of 1s tells SciPy that EVERY variable must be an integer.
        integrality = np.ones(num_vars) 
        
        # Combine integrality with [0.0, 1.0] bounds to create pure binary (0 or 1) variables.
        bounds = Bounds(np.zeros(num_vars), np.ones(num_vars))
        
        # ---------------------------------------------------------------------
        # 4. FIRE UP THE SOLVER
        # Run the branch-and-bound optimizer to find the global minimum.
        # ---------------------------------------------------------------------
        res = milp(c=np.array(c), constraints=constraints, integrality=integrality, bounds=bounds)
        
        if res.success:
            # Reshape the flat array of 1s and 0s back into a clean (N x 3) grid
            decision_matrix = res.x.reshape(N, 3)
            # Find which column index holds the '1' for each car row and return as a list
            # 0 = Local Edge, 1 = Fog Layer, 2 = Cloud Infrastructure
            return np.argmax(decision_matrix, axis=1).tolist()
            
        # Emergency Fallback: If the optimization fails or times out, 
        # default everyone to local execution to keep the cars running safely.
        return [0] * N