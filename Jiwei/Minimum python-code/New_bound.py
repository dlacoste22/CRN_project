#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
import re
import numpy as np
import time
import random
import pandas as pd
import glob
import shutil
import seaborn as sns
import itertools
import math
from pathlib import Path
import json
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

from matplotlib.lines import Line2D
from scipy.integrate import solve_ivp
from sklearn.metrics import confusion_matrix
from scipy.stats import gaussian_kde
from scipy.signal import find_peaks
from autocatalytic_cores_lib import *
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import linregress
from scipy.optimize import newton_krylov
from scipy.optimize import broyden1
from scipy.optimize import anderson
from scipy.optimize._nonlin import NoConvergence
from sympy import symbols, Matrix, diff, lambdify
from scipy.linalg import eigvals
from numpy.linalg import svd
from scipy.optimize import linprog
from scipy.sparse import csr_matrix
from scipy.sparse import bmat
from scipy.sparse.csgraph import connected_components
from scipy.linalg import eigh
from scipy.optimize import fsolve
from textwrap import dedent
import networkx as nx   
from matplotlib import animation


# In[7]:


class Neumann(object):

    """
    This class describes the Generalized von Neumann growth model as it was
    discussed in Kemeny et al. (1956, ECTA) and Gale (1960, Chapter 9.5):

    Let:
    n ... number of goods
    m ... number of activities
    A ... input matrix is m-by-n
        a_{i,j} - amount of good j consumed by activity i
    B ... output matrix is m-by-n
        b_{i,j} - amount of good j produced by activity i

    x ... intensity vector (m-vector) with non-negative entries
        x'B - the vector of goods produced
        x'A - the vector of goods consumed
    p ... price vector (n-vector) with non-negative entries
        Bp - the revenue vector for every activity
        Ap - the cost of each activity

    Both A and B have non-negative entries. Moreover, we assume that
    (1) Assumption I (every good which is consumed is also produced):
        for all j, b_{.,j} > 0, i.e. at least one entry is strictly positive
    (2) Assumption II (no free lunch):
        for all i, a_{i,.} > 0, i.e. at least one entry is strictly positive

    Parameters
    ----------
    A : array_like or scalar(float)
        Part of the state transition equation.  It should be `n x n`
    B : array_like or scalar(float)
        Part of the state transition equation.  It should be `n x k`
    """

    def __init__(self, A, B):

        self.A, self.B = list(map(self.convert, (A, B)))
        self.m, self.n = self.A.shape

        # Check if (A, B) satisfy the basic assumptions
        assert self.A.shape == self.B.shape, 'The input and output matrices \
              must have the same dimensions!'
        assert (self.A >= 0).all() and (self.B >= 0).all(), 'The input and \
              output matrices must have only non-negative entries!'

        # (1) Check whether Assumption I is satisfied:
        if (np.sum(B, 0) <= 0).any():
            self.AI = False
        else:
            self.AI = True

        # (2) Check whether Assumption II is satisfied:
        if (np.sum(A, 1) <= 0).any():
            self.AII = False
        else:
            self.AII = True

    def __repr__(self):
        return self.__str__()

    def __str__(self):

        me = """
        Generalized von Neumann expanding model:
          - number of goods          : {n}
          - number of activities     : {m}

        Assumptions:
          - AI:  every column of B has a positive entry    : {AI}
          - AII: every row of A has a positive entry       : {AII}

        """
        # Irreducible                                       : {irr}
        return dedent(me.format(n=self.n, m=self.m,
                                AI=self.AI, AII=self.AII))

    def convert(self, x):
        """
        Convert array_like objects (lists of lists, floats, etc.) into
        well-formed 2D NumPy arrays
        """
        return np.atleast_2d(np.asarray(x))


    def bounds(self):
        """
        Calculate the trivial upper and lower bounds for alpha (expansion rate)
        and beta (interest factor). See the proof of Theorem 9.8 in Gale (1960)
        """

        n, m = self.n, self.m
        A, B = self.A, self.B

        f = lambda α: ((B - α * A) @ np.ones((n, 1))).max()
        g = lambda β: (np.ones((1, m)) @ (B - β * A)).min()

        UB = fsolve(f, 1).item()  # Upper bound for α, β
        LB = fsolve(g, 2).item()  # Lower bound for α, β

        return LB, UB


    def zerosum(self, γ, dual=False):
        """
        Given gamma, calculate the value and optimal strategies of a
        two-player zero-sum game given by the matrix

                M(gamma) = B - gamma * A

        Row player maximizing, column player minimizing

        Zero-sum game as an LP (primal --> α)

            max (0', 1) @ (x', v)
            subject to
            [-M', ones(n, 1)] @ (x', v)' <= 0
            (x', v) @ (ones(m, 1), 0) = 1
            (x', v) >= (0', -inf)

        Zero-sum game as an LP (dual --> beta)

            min (0', 1) @ (p', u)
            subject to
            [M, -ones(m, 1)] @ (p', u)' <= 0
            (p', u) @ (ones(n, 1), 0) = 1
            (p', u) >= (0', -inf)

        Outputs:
        --------
        value: scalar
            value of the zero-sum game

        strategy: vector
            if dual = False, it is the intensity vector,
            if dual = True, it is the price vector
        """

        A, B, n, m = self.A, self.B, self.n, self.m
        M = B - γ * A

        if dual == False:
            # Solve the primal LP (for details see the description)
            # (1) Define the problem for v as a maximization (linprog minimizes)
            c = np.hstack([np.zeros(m), -1])

            # (2) Add constraints :
            # ... non-negativity constraints
            bounds = tuple(m * [(0, None)] + [(None, None)])
            # ... inequality constraints
            A_iq = np.hstack([-M.T, np.ones((n, 1))])
            b_iq = np.zeros((n, 1))
            # ... normalization
            A_eq = np.hstack([np.ones(m), 0]).reshape(1, m + 1)
            b_eq = 1

            res = linprog(c, A_ub=A_iq, b_ub=b_iq, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds)

        else:
            # Solve the dual LP (for details see the description)
            # (1) Define the problem for v as a maximization (linprog minimizes)
            c = np.hstack([np.zeros(n), 1])

            # (2) Add constraints :
            # ... non-negativity constraints
            bounds = tuple(n * [(0, None)] + [(None, None)])
            # ... inequality constraints
            A_iq = np.hstack([M, -np.ones((m, 1))])
            b_iq = np.zeros((m, 1))
            # ... normalization
            A_eq = np.hstack([np.ones(n), 0]).reshape(1, n + 1)
            b_eq = 1

            res = linprog(c, A_ub=A_iq, b_ub=b_iq, A_eq=A_eq, b_eq=b_eq,
                          bounds=bounds)

        if res.status != 0 or res.x is None:
            # LP infeasible or error
            return np.nan, None

        # Pull out the required quantities
        value = res.x[-1]
        strategy = res.x[:-1]

        return value, strategy


    def expansion(self, tol=1e-8, maxit=1000):
        """
        The algorithm used here is described in Hamburger-Thompson-Weil
        (1967, ECTA). It is based on a simple bisection argument and utilizes
        the idea that for a given γ (= α or β), the matrix "M = B - γ * A"
        defines a two-player zero-sum game, where the optimal strategies are
        the (normalized) intensity and price vector.

        Outputs:
        --------
        alpha: scalar
            optimal expansion rate
        """

        LB, UB = self.bounds()

        for iter in range(maxit):

            γ = (LB + UB) / 2
            ZS = self.zerosum(γ=γ, dual=False)
            V = ZS[0]     # value of the game with γ

            if V >= 0:
                LB = γ
            else:
                UB = γ

            if abs(UB - LB) < tol:
                γ = (UB + LB) / 2
                x = self.zerosum(γ=γ)[1]
                p = self.zerosum(γ=γ, dual=True)[1]
                break

        return γ, x, p

    def interest(self, tol=1e-8, maxit=1000):
        """
        The algorithm used here is described in Hamburger-Thompson-Weil
        (1967, ECTA). It is based on a simple bisection argument and utilizes
        the idea that for a given gamma (= alpha or beta),
        the matrix "M = B - γ * A" defines a two-player zero-sum game,
        where the optimal strategies are the (normalized) intensity and price
        vector

        Outputs:
        --------
        beta: scalar
            optimal interest rate
        """

        LB, UB = self.bounds()

        for iter in range(maxit):
            γ = (LB + UB) / 2
            ZS = self.zerosum(γ=γ, dual=True)
            V = ZS[0]

            if V > 0:
                LB = γ
            else:
                UB = γ

            if abs(UB - LB) < tol:
                γ = (UB + LB) / 2
                p = self.zerosum(γ=γ, dual=True)[1]
                x = self.zerosum(γ=γ)[1]
                break

        return γ, x, p

def compute_von_neumann_alpha_beta(S_plus, S_minus, tol=1e-8):
    """
    Compute von Neumann alpha (expansion), beta (interest),
    and the optimal normalized flows for both problems.

    Returns:
    --------
    alpha : Optimal expansion rate.
    beta : Optimal interest rate.
    x_alpha : Optimal intensity vector (normalized flow) for expansion.
    p_alpha : Optimal price vector for expansion.
    x_beta : Optimal intensity vector (normalized flow) for interest.
    p_beta : Optimal price vector for interest.
    """
    
    A = S_minus.T
    B = S_plus.T
    model = Neumann(A, B)

    # alpha
    alpha, x_alpha, p_alpha = model.expansion(tol=tol)

    # beta
    beta, x_beta, p_beta  = model.interest(tol=tol)

    return alpha, beta, x_alpha, p_alpha, x_beta, p_beta


# In[8]:


'''
Praful MGF
'''
import algorithm_1 as algo1
import auxiliary_functions as aux
# import algorithm_3 as algo3


# In[9]:


def Generate_Random_Network(N_Y_raw, N_R_raw, ambiguity, max_order_f, max_order_b):

    # Build Random Network
    S_raw = np.zeros((N_Y_raw, N_R_raw))
    S1_raw = np.zeros((N_Y_raw, N_R_raw))
    
    # Construct stoichiometric matrix
    for i in range(N_R_raw):
        species1 = random.randint(0, N_Y_raw - 1)
        S_raw[species1][i] += 1
        
        species2 = random.randint(0, N_Y_raw - 1)
        while not ambiguity and species2 == species1:
            species2 = random.randint(0, N_Y_raw - 1)
        S1_raw[species2][i] += 1
            
        # The order of a chemical reaction
        total_order_for = random.randint(1, max_order_f)
        total_order_bac = random.randint(1, max_order_b)
        # Count the number of forward/backward reaction species already in the reaction
        stoichio_for = 0
        stoichio_bac = 0
                
        while stoichio_for < (total_order_for - 1):
            species = random.randint(0, N_Y_raw - 1)
            if ambiguity or S1_raw[species][i] == 0:
                S_raw[species][i] += 1
                stoichio_for += 1
    
        while stoichio_bac < (total_order_bac - 1):
            species = random.randint(0, N_Y_raw - 1)
            if ambiguity or S_raw[species][i] == 0:
                S1_raw[species][i] += 1
                stoichio_bac += 1
    
    Stot_raw = S1_raw - S_raw

    '''
    Reduce Matrix to Avoid Redundant and Confusion
    '''
    
    # Remove all-zero rows (empty species)
    # Species
    row_keep = ~((S_raw==0).all(axis=1) & (S1_raw==0).all(axis=1))
    S_raw  = S_raw[row_keep]
    S1_raw = S1_raw[row_keep]

    # Remove all-zero columns (reactions with net zero stoichiometry)
    col_keep = ~((S_raw==0).all(axis=0) & (S1_raw==0).all(axis=0))
    S_raw  = S_raw[:, col_keep]
    S1_raw = S1_raw[:, col_keep]

    # Remove duplicate columns
    m = S_raw.shape[1]
    keep = []
    seen = set()
    for j in range(m):
        key = tuple(S_raw[:,j].tolist()) + tuple(S1_raw[:,j].tolist())
        if key not in seen:
            seen.add(key)
            keep.append(j)
    S_raw  = S_raw[:, keep]
    S1_raw = S1_raw[:, keep]

    '''
    # === Filter minimal stoichiometry for identical channels ===
    def filter_minimal_channels(S_minus, S_plus):
        # Keep only smallest stoichiometry for channels with identical reactants or products
        m = S_minus.shape[1]
        keep = set(range(m))
        # Group by reactant signature (columns of S_minus)
        reactant_cols = [tuple(col) for col in S_minus.T]
        for i, sig in enumerate(reactant_cols):
            # Find all channels with same reactants
            group = [j for j, s in enumerate(reactant_cols) if s == sig]
            # From these channels, keep minimal stoich for each unique single-species product
            prod_entries = []  # (j, species, count)
            for j in group:
                prod_vec = S_plus[:, j]
                nz = np.nonzero(prod_vec)[0]
                if len(nz) == 1:
                    prod_entries.append((j, nz[0], prod_vec[nz[0]]))
            if len(prod_entries) > 1:
                # Group by product species
                by_prod = {}
                for j, k, count in prod_entries:
                    by_prod.setdefault(k, []).append((j, count))
                # For each product species, keep minimal count
                for entries in by_prod.values():
                    if len(entries) > 1:
                        j_min, _ = min(entries, key=lambda x: x[1])
                        for j, _ in entries:
                            if j != j_min:
                                keep.discard(j)
        return keep

    # Apply filtering for forward channels (filtering by S_raw reactants)
    keep_fwd = filter_minimal_channels(S_raw, S1_raw)
    # Apply filtering for backward channels (filtering by S1_raw as reactants)
    keep_bwd = filter_minimal_channels(S1_raw, S_raw)
    # Intersection: channels to keep
    keep_indices = keep_fwd.intersection(keep_bwd)

    # Filter columns
    keep_list = sorted(keep_indices)
    S_raw = S_raw[:, keep_list]
    S1_raw = S1_raw[:, keep_list]
    '''

    # Record new parameters
    S_plus = S1_raw
    S_minus = S_raw
    Stot = S_plus - S_minus
    N_Y = Stot.shape[0]
    N_R = Stot.shape[1]

    df_Stot = pd.DataFrame(
    Stot.astype(int),                        
    index=range(1, Stot.shape[0]+1),         
    columns=range(1, Stot.shape[1]+1)        
    )
    #print("Matrix Stot:")
    #print(df_Stot.to_string())
    
    # S_plus 
    df_Sp = pd.DataFrame(
        S_plus.astype(int),
        index=range(1, S_plus.shape[0]+1),
        columns=range(1, S_plus.shape[1]+1)
    )
    #print("\nS_plus:")
    #print(df_Sp.to_string())
    
    # S_minus 
    df_Sm = pd.DataFrame(
        S_minus.astype(int),
        index=range(1, S_minus.shape[0]+1),
        columns=range(1, S_minus.shape[1]+1)
    )
    #print("\nS_minus:")
    #print(df_Sm.to_string())
    #print("NY =", N_Y)
    #print("NR =", N_R)

    return Stot, N_Y, N_R, S_plus, S_minus


# In[10]:


"""
We only consider forward reactions,
we don't need to define chemical potential and delta G
"""

def Construct_Kinetics(N_Y, N_R, S_plus, S_minus, degradation=False):
    """
      - Initial concentration Y0
      - Generalized Forward Rate constant kf
      - Degradation kd
    """
    Y0 = [random.uniform(1, 100.0) for _ in range(N_Y)]

    kf = np.array([random.uniform(1e-12, 1.0) for _ in range(N_R)])
    #kf = np.array([(1.0) for _ in range(N_R)])

    kf /= kf.max()
    
    # degradation degradation coefficient
    kd = None
    if degradation:
        kd = 0.01 * np.array([random.uniform(0.95, 1.05) for _ in range(N_Y)])

    return np.array(Y0), kf, kd


# In[11]:


def make_dydt_rescaled_func(N_Y, N_R, S_minus, S_plus, kf, kd, law = "MA"):
    eps=1e-12
    lambdas = []
        
    # net stoichiometry in the free (Y) part for each reaction l
    netStoich_Y = np.zeros(N_R, dtype=int)
    for l in range(N_R):
        netStoich_Y[l] = int(np.sum(S_plus[0:, l]) - np.sum(S_minus[0:, l]))

    def dydt_rescaled(t, Y_star_full):
        Ys = Y_star_full[:N_Y]      # normalized Y^*(t)
        Ys = np.clip(Ys, eps, None) 
        Ys /= Ys.sum()
        
        logN = Y_star_full[-1]      # logN(t)

        net_flux = np.zeros(N_R)

        for l in range(N_R):
            # --- forward flux density using Ystar ---
            prodY = 1.0
            for j in range(N_Y):
                p = S_minus[j, l]
                if p>0:
                    prodY *= Ys[j]**p

            if np.sum(S_minus[0:, l])==0:
                v_f = 0.0
            else:
                if law=="MM":
                    Kf = prodY
                    v_f = 0.0 if (kf[l]+Kf)==0 else Kf/(kf[l]+Kf)
                else:
                    v_f = kf[l]*prodY

            net_flux[l] = v_f
            
        lambda_t = float(np.dot(net_flux, netStoich_Y))
        lambdas.append(lambda_t)

        # dY*/dt
        dYs = np.zeros(N_Y)
        for j in range(N_Y):
            row = S_plus[j,:] - S_minus[j,:]
            dYs[j] = float(np.dot(row, net_flux)) - lambda_t*Ys[j]

        # d(logN)/dt = lambda(t)
        return np.concatenate([dYs, [lambda_t]])

    return dydt_rescaled, lambdas
    
def Solve_Scaled_System(S_minus, S_plus, Y0, N_Y, N_R,
                        kf, kd, dt, n_steps, threshold, extra_steps, law = "MA"):
    """
    Fix step dt，simulate n_steps：
      - t_eval      (length = n_steps+1)
      - Ystar_traj  (shape (N_Y, n_steps+1))
      - Yabs_traj   (shape (N_Y, n_steps+1))
      - lambdas     (length = n_steps+1)
      - N_traj      (length = n_steps+1)
    """
    def single_run(Y0, n_steps):
        # initialize N, normalize Y*
        N0 = np.sum(Y0)
        Ystar0 = Y0 / N0
        logN0 = math.log(N0)
        y0 = np.concatenate([Ystar0, [logN0]])
    
        ttot = dt * n_steps
        t_eval = np.linspace(0, ttot, n_steps + 1)
    
        dydt_rescaled, lambdas = make_dydt_rescaled_func(
            N_Y, N_R, S_minus, S_plus, kf, kd, law
        )
    
        sol = solve_ivp(
            fun=lambda t, y: dydt_rescaled(t, y),
            t_span=[0, ttot],
            y0=y0,
            method="LSODA",
            dense_output=False,
            t_eval=t_eval,
            rtol=1e-6,
            atol=1e-8
        )
    
        Ystar_traj = sol.y[:N_Y, :]             # normalize Y^*(t)
        logN_traj = sol.y[N_Y, :]               # logN(t)
        N_traj = np.exp(logN_traj)              # exact N(t)
        Yabs_traj = Ystar_traj * N_traj         # exact Y(t) = N(t)*Y^*(t)
    
        return t_eval, Ystar_traj, Yabs_traj, lambdas, N_traj, dydt_rescaled

    t_eval, Ystar_traj, Yabs_traj, lambdas, N_traj, dydt_rescaled = single_run(Y0, n_steps)

    """
    compute the residual of differencial equation and check if it reach the convergence requirement
    and add additional steps if not
    """
    
    while True:
        # the last time point
        q_final = Ystar_traj[:, -1]
        lambda_final = lambdas[-1]
        logN_final = math.log(N_traj[-1])
        # compute residual dY*/dt
        d_full = dydt_rescaled(0.0, np.concatenate([q_final, [logN_final]]))
        residual = np.max(np.abs(d_full[:N_Y]))
        if residual < threshold:
            break

        # if need to run extra_steps
        Y0_new = Yabs_traj[:, -1]
        t_ext, Ystar_ext, Yabs_ext, lambda_ext, N_ext, _ = single_run(Y0_new, extra_steps)

        # conjugate data
        t_ext_shifted = t_ext[1:] + t_eval[-1]
        t_eval = np.concatenate([t_eval, t_ext_shifted])
        Ystar_traj = np.hstack([Ystar_traj, Ystar_ext[:, 1:]])
        Yabs_traj  = np.hstack([Yabs_traj,  Yabs_ext[:,  1:]])
        lambdas    = lambdas + lambda_ext[1:]
        N_traj     = np.concatenate([N_traj, N_ext[1:]])

    return t_eval, Ystar_traj, Yabs_traj, lambdas, N_traj
    
# =============================================================================
# long-term growth rate
# =============================================================================
def compute_long_term_growth_rate(lambdas):
    """
    Average the last last_n values of the lambda(t) sequence to obtain an estimate of the exponential growth rate λ
    """
    if len(lambdas) == 0:
       return 0.0
    return lambdas[-1]


# In[12]:


def solve_steadystate_by_newton_krylov(
    S_plus, S_minus, N_Y, N_R, Y0, kf,
    law='MA',
    dt=1e-3, n_steps=20000,
    tol=1e-7, maxiter=5000, inner_maxiter=200): 
    '''
    Perform time-dependent simulation until t = dt * n_steps, obtaining initial q0, lambda0.
    Solve F(q,λ)=0 using Newton–Krylov, with parameterization ensuring q ∈ simplex.
    '''
    # =============================================================================
    # —— Simulation for some steps to get initial condition for equation —— 
    # =============================================================================
    lambdas = []
    Y0 = np.asarray(Y0, float)
    N0 = Y0.sum()
    Ystar0 = Y0 / N0
    logN0 = np.log(N0)
    y0 = np.concatenate([Ystar0, [logN0]])

    # netStoich
    netStoich_Y = np.zeros(N_R, dtype=int)
    for l in range(N_R):
        netStoich_Y[l] = int(np.sum(S_plus[0:, l]) - np.sum(S_minus[0:, l]))

    def dydt_rescaled(t, y):
        Ys = y[:N_Y]
        Ys = np.clip(Ys, 1e-12, None)
        Ys /= Ys.sum()
        
        net_flux = np.zeros(N_R)

        for l in range(N_R):
            # --- forward flux density using Ystar ---
            prodY = 1.0
            for j in range(N_Y):
                p = S_minus[j, l]
                if p>0:
                    prodY *= Ys[j]**p

            if np.sum(S_minus[0:, l])==0:
                v_f = 0.0
            else:
                if law=="MM":
                    Kf = prodY
                    v_f = 0.0 if (kf[l]+Kf)==0 else Kf/(kf[l]+Kf)
                else:
                    v_f = kf[l]*prodY

            net_flux[l] = v_f
            
        lambda_t = float(np.dot(net_flux, netStoich_Y))
        lambdas.append(lambda_t)

        # dY*/dt
        dYs = np.zeros(N_Y)
        for j in range(N_Y):
            row = S_plus[j,:] - S_minus[j,:]
            dYs[j] = float(np.dot(row, net_flux)) - lambda_t*Ys[j]

        # d(logN)/dt = lambda(t)
        return np.concatenate([dYs, [lambda_t]])

    ttot = dt * n_steps
    t_eval = np.linspace(0, ttot, n_steps + 1)
    sol = solve_ivp(
        fun=dydt_rescaled,
        t_span=[0, ttot],
        y0=y0,
        method="LSODA",
        t_eval=t_eval,
        rtol=1e-6, atol=1e-8
    )
    Ystar_traj = sol.y[:N_Y, :]
    Ys_final = Ystar_traj[:, -1]

    # initial guess q0, lambda0
    q0 = np.clip(Ys_final, 1e-12, None)
    q0 /= q0.sum()
    J0 = np.array([
        kf[r] * np.prod(q0**S_minus[:, r])
        for r in range(N_R)
    ])
    lam0 = float(netStoich_Y.dot(J0))

    # =============================================================================
    # —— Newton–Krylov solve steady state equation —— 
    #    Parameterization: u_vars ∈ ℝ^(N_Y-1)， λ ∈ ℝ
    # =============================================================================

    # construct residual: x = [u_vars (N_Y-1), λ]
    def residual_mapped(x):
        u_vars = x[:N_Y-1]
        lam = x[N_Y-1]
        # rebuild u_full, set u_N=0
        u_full = np.concatenate([u_vars, [0.0]])
        # use softmax projection to q
        expu = np.exp(u_full - u_full.max())
        q = expu / expu.sum()
        # compute flow
        J = np.array([
            kf[r] * np.prod(q**S_minus[:, r])
            for r in range(N_R)
        ])
        # F(q, λ) = S*J - λ*q
        return (S_plus - S_minus).dot(J) - lam * q

    # initial x0: use q0 project back to u0_vars
    u0_full = np.log(q0)
    # gauge: set u_N = 0, others minus u_N
    u0_vars = u0_full[:-1] - u0_full[-1]
    x0 = np.concatenate([u0_vars, [lam0]])
    
    try:
        sol_nk = newton_krylov(
            residual_mapped,
            x0,
            method='lgmres',
            inner_maxiter=inner_maxiter,
            f_tol=tol,
            maxiter=maxiter,
            line_search=True,
        )
        
    except Exception as e_krylov:
        sol_nk = broyden1(
            residual_mapped,
            x0,
            f_tol=tol,
            maxiter=maxiter
        )
        
    except Exception as e_broyden:
        sol_nk = anderson(
            residual_mapped,
            x0,
            f_tol=tol,
            maxiter=maxiter
        )

    # slove q*, λ*
    u_star_vars = sol_nk[:N_Y-1]
    lam_star   = sol_nk[N_Y-1]
    u_star_full = np.concatenate([u_star_vars, [0.0]])
    expu = np.exp(u_star_full - u_star_full.max())
    q_star = expu / expu.sum()

    # final J_star
    J_star = np.array([
        kf[r] * np.prod(q_star**S_minus[:, r])
        for r in range(N_R)
    ])

    return q_star, lam_star, J_star


# In[13]:


# compute the topological growth bound
def compute_topological_growth_bound(S_minus, alpha):
    row_sums = np.sum(S_minus, axis=1)
    S_minus_norm = np.max(row_sums)
    mu = S_minus_norm * (alpha - 1)
    return mu

# compute the lower topological growth bound
def compute_lower_topological_growth_bound(S_minus):
    row_sums = np.sum(S_minus, axis=1)
    S_minus_norm = np.max(row_sums)
    mu = - S_minus_norm
    return mu


# # Random network

# In[14]:


def main_example():

    '''
    N_Y_raw, N_R_raw = 4, 5
    while True:
        Stot, N_Y, N_R, S_plus, S_minus = Generate_Random_Network(
            N_Y_raw, N_R_raw, ambiguity=False, max_order_f = 1, max_order_b = 2
        )
    '''

    S_plus = np.array([
        [0, 0, 0, 1, 0],
        [1, 0, 0, 0, 1],
        [0, 1, 0, 1, 0],
        [0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0]])
    S_minus = np.array([
        [2, 0, 0, 0, 1], 
        [0, 0, 0, 1, 0],
        [0, 0, 2, 0, 0],
        [0, 0, 0, 1, 1],
        [0, 1, 0, 0, 0]])

    Stot = S_plus - S_minus
    N_Y = 5
    N_R = 5
    _, _, auto = aux.checkAutonomy(S_minus, S_plus)
    if auto:
        print("Found an autonomous network.")
        #break

    wTS = Stot.sum(axis=0)
    eps_sign = 1e-6
    if np.all(np.abs(wTS) <= eps_sign):
        wTS_cat = "all_zero"      
    elif np.all(wTS >= -eps_sign):
        wTS_cat = "all_nonneg"     
    elif np.all(wTS <= eps_sign):
        wTS_cat = "all_nonpos"     
    else:
        wTS_cat = "mixed"
            
    print(f"NY = {N_Y}")
    print(f"NR = {N_R}")
    print(f"wTS = {wTS_cat}")
    
    Y0, kf, kd = Construct_Kinetics(
        N_Y, N_R, S_plus, S_minus, degradation=False
    )
    
    alpha, beta, x_alpha, p_alpha, x_beta, p_beta = compute_von_neumann_alpha_beta(S_plus, S_minus)
    mu = compute_topological_growth_bound(S_minus, alpha)
    mu_l = compute_lower_topological_growth_bound(S_minus)
    print(f"α = {alpha:.5f},  β = {beta:.5f}, μ = {mu:.5f}, mu_low = {mu_l:.5f}")


    '''
    sum_xb = x_beta.sum()
    if sum_xb <= 0:
        print("Warning: sum(x_beta) <= 0, skip flux-based growth check.")
    else:
        scale = 1.0 / sum_xb              # sum(x_beta) = 1
        x_beta_norm = x_beta * scale
        x_alpha_scaled = x_alpha * scale  # scale x_alpha

        print(f"sum(x_beta_norm) = {x_beta_norm.sum():.5f}")

        net_change = Stot @ x_alpha_scaled 
        lambda_vN = net_change.sum()          

        print(f"lambda_vN = {lambda_vN:.5f}")
        print(f"lambda_vN - μ = {lambda_vN - mu:.5e}")

    '''
    
    try:
        q_star, lambda_long, J_star = solve_steadystate_by_newton_krylov(
                S_plus, S_minus, N_Y, N_R, Y0, kf)
    
    except NoConvergence:        
        dt = 1e-4
        n_steps = 2000000
        threshold = 1e-4
        extra_steps = 100000
        t_eval, Ystar_traj, Yabs_traj, lambdas, N_traj = Solve_Scaled_System(
            S_minus, S_plus, Y0, N_Y, N_R,
            kf, kd, dt, n_steps, threshold, extra_steps, law = "MA")
        
        lambda_long = compute_long_term_growth_rate(lambdas)
    
    # long-term growth rate
    print(f"Kinetics = {kf}\n")
    print(f"Estimated long-term growth rate λ ≈ {lambda_long:.5f}\n")
    print(f"Final Concentration ≈ {q_star}\n")
    print(f"Final Flux ≈ {J_star}\n")
    

# run
#if __name__ == "__main__":
#    main_example()


# In[15]:


def save_all_results(base_folder,
                     growth_list,
                     S_plus_list, S_minus_list,
                     kf_list, kd_list):
    os.makedirs(base_folder, exist_ok=True)

    # 1) Growth factors table
    df_growth = pd.DataFrame(growth_list).sort_values('realization')
    df_growth.to_csv(os.path.join(base_folder, 'growth_factors.dat'),
                     sep='\t', index=False)

    # 2) Formatted stoichiometric matrices, one file with all realizations
    fmt_path = os.path.join(base_folder, 'stoichiometries_formatted.txt')
    with open(fmt_path, 'w') as f:
        for rec, S_plus, S_minus in zip(growth_list, S_plus_list, S_minus_list):
            i = rec['realization']
            f.write(f"# Realization {i}\n")

            # S_plus
            df_sp = pd.DataFrame(
                S_plus.astype(int),
                index=range(1, S_plus.shape[0]+1),
                columns=range(1, S_plus.shape[1]+1)
            )
            f.write("S_plus:\n")
            f.write(df_sp.to_string())
            f.write("\n\n")

            # S_minus
            df_sm = pd.DataFrame(
                S_minus.astype(int),
                index=range(1, S_minus.shape[0]+1),
                columns=range(1, S_minus.shape[1]+1)
            )
            f.write("S_minus:\n")
            f.write(df_sm.to_string())
            f.write("\n\n")

    # 3) Kinetics and initial concentrations table (long format)
    kin_records = []
    for rec, kf, kd in zip(growth_list, kf_list, kd_list):
        i = rec['realization']
        # kf
        for idx, val in enumerate(kf):
            kin_records.append({
                'realization': i,
                'parameter': 'kf',
                'index': idx,
                'value': float(val)
            })
        # kd (ensure iterable)
        kd_array = kd if kd is not None else np.full_like(kf, np.nan)
        for idx, val in enumerate(kd_array):
            kin_records.append({
                'realization': i,
                'parameter': 'kd',
                'index': idx,
                'value': float(val)
            })

    df_kin = pd.DataFrame(kin_records) \
               .sort_values(['realization','parameter','index'])
    df_kin.to_csv(os.path.join(base_folder, 'kinetics.dat'),
                  sep='\t', index=False)


# In[25]:


'''
Stoichometric autocatalytic and dynamic growth

Systems for maximum chemical reaction order = 2

With autonomous check for matrix without X species

With the check w^T · S
'''

def main_order2():

    # how many of each category
    quota_ge1 = 3000   # α >= 1  (merge α=1 and α>1)
    quota_lt1 = 2500   # α < 1
    total_target = quota_ge1 + quota_lt1
    next_pct = 10
    
    # counters
    count_ge1 = 0
    count_lt1 = 0

    tol_alpha = 1e-4  # classification tolerance, keep consistent everywhere

    # storage
    results_gt1 = []
    results_eq1 = []
    results_lt1 = []

    # counters
    count_gt1 = 0
    count_eq1 = 0
    count_lt1 = 0
    
    # storage
    alpha_list = []
    beta_list = []
    lambda_list = []
    mu_list = []
    mu_l_list = []
    growth_list = []
    S_plus_list = []
    S_minus_list = []
    kf_list = []; kd_list = []
    delta_list = []
    u_list = []              # u(S) = max(0, alpha-1)
    B_list = []              # B(S) = ||S_-|| * ||k||
    lam_tilde_list = [] 
    
    attempts = 0       
    successes = 0       
    
    # number of trail
    while attempts < 150000:
        attempts += 1
        
        # Random networks (change the oder here)
        Stot, N_Y, N_R, S_plus, S_minus = Generate_Random_Network(
        N_Y_raw=random.randint(2, 12),
        N_R_raw=random.randint(2, 12),
        ambiguity=False,
        max_order_f = 2,
        max_order_b = 2
        )

        # Check autonomy condition
        _, _, auto = aux.checkAutonomy(S_minus, S_plus)
        if not auto:
            continue
         
        # von Neumann growth factor α, β
        try:
            alpha, beta, x_alpha, p_alpha, x_beta, p_beta = compute_von_neumann_alpha_beta(S_plus, S_minus)
        except Exception:
            continue
        if np.isnan(alpha) or np.isnan(beta):
            continue

        delta = alpha - 1.0

        # check which quota this alpha would fill — skip if full
        if delta < -tol_alpha:
            if count_lt1 >= quota_lt1:
                continue
        else:
            # delta >= -tol_alpha  --> treat as alpha >= 1 class (includes alpha≈1)
            if count_ge1 >= quota_ge1:
                continue
            
        mu = compute_topological_growth_bound(S_minus, alpha)
        if abs(mu) < 1e-3:
            mu = 0.0

        mu_l = compute_lower_topological_growth_bound(S_minus)
        if abs(mu_l) < 1e-3:
            mu_l = 0.0
        
        # Kinetics
        Y0, kf, kd = Construct_Kinetics(
            N_Y, N_R, S_plus, S_minus, degradation=False
        )
        
        try:
            q_star, lambda_long, J_star = solve_steadystate_by_newton_krylov(
                    S_plus, S_minus, N_Y, N_R, Y0, kf)
        
        except NoConvergence:        
            dt = 1e-4
            n_steps = 2000000
            threshold = 1e-4
            extra_steps = 100000
            t_eval, Ystar_traj, Yabs_traj, lambdas, N_traj = Solve_Scaled_System(
                S_minus, S_plus, Y0, N_Y, N_R,
                kf, kd, dt, n_steps, threshold, extra_steps, law = "MA")
            
            lambda_long = compute_long_term_growth_rate(lambdas)
        
        
        if not (np.isfinite(mu) and np.isfinite(lambda_long)):
            continue

        # ---------- Normalization for the universal bound ----------
        # u(S) = max(0, alpha - 1)
        delta = alpha - 1.0
        u = max(0.0, delta)

        # Norm S-
        row_sums = np.sum(S_minus, axis=1)
        S_minus_norm = np.max(row_sums)

        # Norm k
        k_norm = 1

        B = S_minus_norm * k_norm
        if not np.isfinite(B) or B < 1e-12:
            continue

        lam_tilde = lambda_long / B
        
        if (delta < -tol_alpha) and (delta > lam_tilde): print(f"[VIOLATION α<1] realization={successes} α={alpha:.6g} δ={delta:.6g} λ~={lam_tilde:.6g} λ={lambda_long:.6g} norm={B:.6g}")
        if (delta >= tol_alpha) and (delta < lam_tilde): print(f"[VIOLATION α≥1] realization={successes} α={alpha:.6g} δ={delta:.6g} λ~={lam_tilde:.6g} λ={lambda_long:.6g} norm={B:.6g}")


        delta_list.append(delta)
        u_list.append(u)
        B_list.append(B)
        lam_tilde_list.append(lam_tilde)
        
        # save
        alpha_list.append(alpha)
        beta_list.append(beta)
        lambda_list.append(lambda_long)
        mu_list.append(mu)
        mu_l_list.append(mu_l)

        growth_list.append({
            'realization': successes,
            'alpha': alpha,
            'beta': beta,
            'mu': mu,
            'mu_low': mu_l,
            'lambda': lambda_long,
            'delta': delta,
            'lambda_tilde': lam_tilde,
            
        })
        S_plus_list.append(S_plus)
        S_minus_list.append(S_minus)
        kf_list.append(kf)
        kd_list.append(kd)
                
        successes = len(alpha_list)

        pct = int(100 * successes / total_target)
        if pct >= next_pct:
            print(f"Progress: {next_pct}% completed ({successes}/{total_target}).")
            next_pct += 10
                
        if delta < -tol_alpha:
            count_lt1 += 1
        else:
            count_ge1 += 1
        
        #print(f"【{successes}/{quota_ge1+quota_lt1}】  α = {alpha:.5f},  β = {beta:.5f}, μ = {mu:.5f},  λ = {lambda_long:.5f}")

        if (count_ge1 >= quota_ge1 and count_lt1 >= quota_lt1):
            print("All quotas reached, stop simulation.")
            break
            
    # check loop        
        #print(f"collect {successes} effective (α, β, mu, λ), end")

    lam_arr = np.array(lambda_list)
    mu_arr = np.array(mu_list)
    mu_l_arr = np.array(mu_l_list)

    # =============================
    # Two figures:
    #   Fig A: alpha < 1  (delta < 0)   bound: delta <= x <= 0
    #   Fig B: alpha >= 1 (delta >= 0)  bound: -1 <= x <= delta   (alpha=1 auto included)
    # x = lambda_tilde, y = delta
    # No titles, no legends
    # Save as two separate PDFs in current folder
    # =============================
    
    # -----------------------
    # Plot settings
    # -----------------------
    tick_fs  = 12   # tick numbers font size
    label_fs = 14   # axis label font size
    
    bins_hist = 50          # histogram bins (you can tune)
    use_hist  = True        # set False if you only want KDE
    use_kde   = False        # set True to overlay KDE curve
    
    tol_alpha = 1e-4        # must match sampling classification
    
    out_dir = "results_order2"
    os.makedirs(out_dir, exist_ok=True)
    
    def pad_range(vmin, vmax, frac=0.07):
        span = vmax - vmin
        if span < 1e-12:
            span = 1.0
        p = frac * span
        return vmin - p, vmax + p
    
    def kde_counts_1d(samples, y_grid, bin_width, bw=None):
        """
        Gaussian KDE (manual) -> returns "expected counts" per bin-width,
        so it overlays nicely with a COUNT histogram.
        """
        samples = np.asarray(samples, dtype=float)
        n = samples.size
        if n < 2:
            return np.zeros_like(y_grid)
    
        std = samples.std(ddof=1)
        if bw is None:
            # Silverman's rule
            bw = 1.06 * std * (n ** (-1/5)) if std > 1e-12 else 1.0
    
        diff = (y_grid[:, None] - samples[None, :]) / bw
        pdf = np.exp(-0.5 * diff**2).sum(axis=1) / (n * bw * np.sqrt(2*np.pi))
    
        # convert density -> expected counts per bin-width
        return pdf * n * bin_width
    
    # -----------------------
    # Data arrays (no re-simulation)
    # -----------------------
    delta_arr = np.array(delta_list, dtype=float)
    lam_tilde_arr = np.array(lam_tilde_list, dtype=float)
    
    mask_lt = delta_arr < -tol_alpha           # alpha < 1
    mask_ge = delta_arr >= -tol_alpha          # alpha >= 1 (includes alpha≈1)
    
    # for clean plotting: force alpha≈1 band to delta=0
    delta_plot = delta_arr.copy()
    delta_plot[np.abs(delta_plot) < tol_alpha] = 0.0
    
    # -----------------------
    # Helper: draw (scatter + feasible shading) + right distribution
    # -----------------------
    def plot_with_right_distribution(x, y, mode, pdf_name):
        """
        mode = "lt"  : alpha<1  bound: y <= x <= 0, y<=0
        mode = "ge"  : alpha>=1 bound: -1 <= x <= y, y>=0
        """
        fig = plt.figure(figsize=(8.5, 5))
        gs = fig.add_gridspec(1, 2, width_ratios=[3.2, 1.0], wspace=0.05)
    
        ax = fig.add_subplot(gs[0, 0])
        axh = fig.add_subplot(gs[0, 1], sharey=ax)
    
        # ---- scatter ----
        if x.size:
            ax.scatter(x, y, s=30, edgecolors='k', alpha=0.9)
    
        # ---- y limits from data (independent per figure) ----
        if y.size:
            ymin, ymax = y.min(), y.max()
            ymin, ymax = pad_range(ymin, ymax)
        else:
            ymin, ymax = (-1.0, 1.0)
        ax.set_ylim(ymin, ymax)
    
        # ---- shading + reference lines (NO legend, NO title) ----
        if mode == "lt":
            # feasible region: for y in [ymin, min(0,ymax)], x in [y, 0]
            y_hi = min(0.0, ymax)
            if ymin < y_hi:
                yy = np.linspace(ymin, y_hi, 400)
                ax.fill_betweenx(yy, yy, 0.0, alpha=0.12)
    
            ax.axvline(0.0, ls='--', color='gray')
            if ymin < 0.0:
                ax.plot([0.0, ymin], [0.0, ymin], ls='--', color='gray')  # y=x from origin into negative
    
            # x limits
            if x.size:
                xmin = min(x.min(), ymin)
            else:
                xmin = ymin
            ax.set_xlim(*pad_range(xmin, 0.0))
    
        elif mode == "ge":
            # feasible region: for y in [max(0,ymin), ymax], x in [-1, y]
            y_lo = max(0.0, ymin)
            if y_lo < ymax:
                yy = np.linspace(y_lo, ymax, 400)
                ax.fill_betweenx(yy, -1.0, yy, alpha=0.12)
    
            ax.axvline(-1.0, ls='--', color='gray')
            if ymax > 0.0:
                ax.plot([0.0, ymax], [0.0, ymax], ls='--', color='gray')  # y=x from origin into positive
    
            # x limits
            if x.size:
                xmax = max(x.max(), ymax)
            else:
                xmax = max(1.0, ymax)
            ax.set_xlim(*pad_range(-1.0, xmax))
    
        # ---- axis labels (font adjustable) ----
        ax.set_xlabel(r'$\tilde{\Lambda}$', fontsize=label_fs)
        ax.set_ylabel(r'$\delta$', fontsize=label_fs)
        ax.grid(linestyle="--", alpha=0.5)
        ax.tick_params(axis='both', which='major', labelsize=tick_fs)
    
        # -----------------------
        # Right distribution: histogram + KDE (frequency on x, delta on y)
        # -----------------------
        axh.grid(linestyle="--", alpha=0.3)
        axh.tick_params(axis='both', which='major', labelsize=tick_fs)
    
        # hide duplicated y tick labels on the right panel (keeps alignment clean)
        plt.setp(axh.get_yticklabels(), visible=False)
    
        if y.size:
            # choose histogram range to match main y-lims
            y_range = ymax - ymin
            bin_width = y_range / bins_hist
    
            if use_hist:
                axh.hist(
                    y,
                    bins=bins_hist,
                    range=(ymin, ymax),
                    orientation="horizontal",
                    density=False,         # frequency counts
                    alpha=0.35,
                    edgecolor="none"
                )
    
            if use_kde:
                yy = np.linspace(ymin, ymax, 400)
                kde_x = kde_counts_1d(y, yy, bin_width=bin_width, bw=None)
                axh.plot(kde_x, yy, lw=1.5)
    
            axh.set_xlabel("count", fontsize=label_fs)
        else:
            axh.set_xlabel("count", fontsize=label_fs)
    
        # save
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, pdf_name), bbox_inches="tight")
      #  plt.show()
    
    # -----------------------
    # FIG A: alpha < 1
    # -----------------------
    xA = lam_tilde_arr[mask_lt]
    yA = delta_plot[mask_lt]
    plot_with_right_distribution(xA, yA, mode="lt", pdf_name="bound_alpha_lt1_with_delta_dist.pdf")
    
    # -----------------------
    # FIG B: alpha >= 1 (merged)
    # -----------------------
    xB = lam_tilde_arr[mask_ge]
    yB = delta_plot[mask_ge]
    plot_with_right_distribution(xB, yB, mode="ge", pdf_name="bound_alpha_ge1_with_delta_dist.pdf")

    save_all_results(
        base_folder='results_order2',
        growth_list=growth_list,
        S_plus_list=S_plus_list,
        S_minus_list=S_minus_list,
        kf_list=kf_list,
        kd_list=kd_list)
    
    #-------------
    #More figs 
    #-----------
    
    #counts, bin_edges, _ = plt.hist(
    #    alpha_list,
    #    bins=100,
    #    density=True,          # <- correct replacement for `normed`
    #    color='tab:green',
    #    alpha=0.5,
    #    edgecolor='tab:green',       # if this ever complains in your env, use edgecolor=None
    #    linewidth=0.5
    #    )

    #plt.xlim(0, 2)
    #plt.xlabel("von Neumann growth factor α", fontsize=12)
    #plt.ylabel("Density", fontsize=12)
    #plt.title("Distribution of α", fontsize=14)
    #plt.grid(linestyle="--", alpha=0.4)
    #plt.tight_layout()
    #plt.savefig(os.path.join(out_dir,"new_fig.pdf"))
    # plt.show()


# In[26]:


#warnings.filterwarnings('ignore', category=RuntimeWarning)
if __name__ == "__main__":
    main_order2()


# In[ ]:




