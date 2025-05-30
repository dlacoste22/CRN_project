# -*- coding: utf-8 -*-
"""
Created on Wed Dec 25 12:43:48 2024

@author: Trabajador
"""

import numpy as np
import gurobipy as gb
import time
import auxiliary_functions as aux

# =============================================================================
def growthRateGraph(output_matrix, input_matrix, max_steps, time_limit_iteration):
    """
    Calculate growth rate and related parameters for a given stoichiometric model.

    Parameters:
    - output_matrix (np.ndarray): The output stoichiometric matrix for reactions.
    - input_matrix (np.ndarray): The input stoichiometric matrix for reactions.
    - max_steps (int): The maximum number of iterations.
    - time_limit_iteration (float): Time limit for each Gurobi optimization step.

    Returns:
    - x_t (np.ndarray): Optimal reaction flows for the final iteration.
    - alpha_t (float): Final calculated growth rate.
    - step (int): Number of iterations completed.
    - alphaDict (dict): Dictionary of alpha values per iteration.
    - total_time (float): Total computation time.
    - results_dict (dict): Detailed results for each iteration.
    """
    
    stoichiometric_matrix = output_matrix - input_matrix
    num_species, num_reactions = stoichiometric_matrix.shape
    x_0 = np.ones(num_reactions)
    
    # Vectorized computation of initial alpha
    initial_alpha_vector = np.sum(output_matrix * x_0, axis=1) / np.maximum(np.sum(input_matrix * x_0, axis=1), 1e-15)
    alpha_0 = np.min(initial_alpha_vector)
    
    # -------------------------------------------------------------------------
    def modelGrowthRateFixed(previous_alpha, time_limit):
        m = gb.Model("Growth_Rate_Model")
        x = m.addVars(num_reactions, lb=0, ub=1000, name="x")
        alpha = m.addVar(name="alpha")
        
        m.setObjective(alpha, gb.GRB.MAXIMIZE)
        
        # Add constraints
        m.addConstrs(
            (alpha <= gb.quicksum(output_matrix[s, r] * x[r] for r in range(num_reactions)) -
             previous_alpha * gb.quicksum(input_matrix[s, r] * x[r] for r in range(num_reactions))
             for s in range(num_species)), name="constraint_growth_rate")
        
        m.addConstrs(
            (gb.quicksum(input_matrix[s, r] * x[r] for r in range(num_reactions)) >= 1 
             for s in range(num_species)
            if sum(input_matrix[s, r] for r in range(num_reactions))),
            name="constraint_min_input")
        
        m.Params.TimeLimit = time_limit
        m.Params.OutputFlag = 0
        m.Params.MIPGap = 0.00
        
        m.optimize()
        
        if m.status != gb.GRB.OPTIMAL:
            raise ValueError("Optimization did not reach optimality. Check infeasibility report.")
        return np.array([x[r].X for r in range(num_reactions)]), alpha.X, m.NumVars, m.NumConstrs
    # -------------------------------------------------------------------------

    stop = False
    step = 0
    alphaDict = {0: alpha_0}
    previous_alpha = alpha_0
    alpha_t = alpha_0
    alpha_old = 0
    start_time = time.time()
    results_dict = {}

    while not stop:
        iteration_start_time = time.time()
        
        x_t, alphabar, num_vars, num_constraints = modelGrowthRateFixed(previous_alpha, time_limit_iteration)
        
        # Vectorized alpha calculation
        alpha_t = np.min(np.sum(output_matrix * x_t, axis=1) / np.maximum(np.sum(input_matrix * x_t, axis=1), 1e-15))
        
        results_dict[step] = {
            "x": x_t,
            "alphabar": alphabar,
            "variables": num_vars,
            "constraints": num_constraints,
            "step": step,
            "alpha": alpha_t,
            "time": time.time() - iteration_start_time
        }

        if (np.abs(alphabar) < 1e-5 or step >= max_steps or np.abs(alpha_old - alpha_t) < 1e-5):
            stop = True
            alphaDict[step] = alpha_t
            total_time = time.time() - start_time
            return x_t, alpha_t, step, alphaDict, total_time, results_dict
        else:
            alphaDict[step] = alpha_t
            step += 1
            previous_alpha = alpha_t
            alpha_old = alpha_t
# =============================================================================


# =============================================================================
def tryGrowthRateGraph(input_matrix, output_matrix, nameScenario, time_limit_iteration, name_species=""):
    """
    Wrapper function to compute and log growth rate graph information.

    Parameters:
    - input_matrix (np.ndarray): Input stoichiometric matrix.
    - output_matrix (np.ndarray): Output stoichiometric matrix.
    - nameScenario (str): Name for output files.
    - time_limit_iteration (float): Time limit per iteration in optimization.
    - name_species (list, optional): Names of species for detailed output.

    Outputs:
    - Writes results to a file.
    """
    max_steps = 1000

    # Check autonomy of the network
    autonomous_species, autonomous_reactions, autonomous_general = aux.checkAutonomy(input_matrix, output_matrix)
    
    
    if not autonomous_general:
        print("Error: The chemical reaction network is not autonomous.")
        return
    
    x, alpha, step, alphaDict, time, dict_a_guardar = growthRateGraph(output_matrix, input_matrix, max_steps, time_limit_iteration)
    
    info = []
    info.append("All information:\n")
    info.append(f"{dict_a_guardar}\n")
    info.append(f"Number of steps: {step}\n")
    info.append(f"Total time: {time:.2f} seconds\n")
    info.append(f"Average time per iteration: {time/step:.2f} seconds\n" if step else "Average time per iteration: ---\n")
    info.append(f"S dimension: {input_matrix.shape}\n")
    info.append(f"Growth factor: {alpha:.6f}\n")
    info.append(f"Flows: {x}\n")
    
    info.append("S reactions:\n")
    row_mapping = {i: i for i in range(input_matrix.shape[0])}
    column_mapping = {j: j for j in range(input_matrix.shape[1])}
    
    if not name_species:
        reactions = recordReactions(output_matrix, input_matrix, x, row_mapping, column_mapping)
        filename = nameScenario + '_algorithm_1.txt'
    else:
        reactions = recordReactionsNamesSpecies(output_matrix, input_matrix, x, row_mapping, column_mapping, name_species)
        filename = nameScenario + '_algorithm_1_with_names.txt'

    info.extend(reactions)
    
    filename = "output/" + filename
    
    with open(filename, 'w') as f:
        for line in info:
            f.write(line)
# =============================================================================


# =============================================================================
def recordReactions(output_matrix, input_matrix, x, row_mapping, column_mapping):
    """
    Generate string representations of chemical reactions from matrix data.

    Parameters:
    - output_matrix (np.ndarray): Output stoichiometric matrix.
    - input_matrix (np.ndarray): Input stoichiometric matrix.
    - x (np.ndarray): Reaction flows.
    - row_mapping (dict): Mapping for species indices.
    - column_mapping (dict): Mapping for reaction indices.

    Returns:
    - List[str]: List of reaction strings.
    """
    num_species, num_reactions = input_matrix.shape
    reactions = []

    for j in range(num_reactions):
        reactants = []
        products = []
        
        # Gather reactants
        for i in range(num_species):
            if input_matrix[i, j] > 0.5:
                coef = int(input_matrix[i, j]) if input_matrix[i, j] > 1 else ''
                reactants.append(f"{coef}s{row_mapping[i] + 1}")
        
        # Gather products
        for i in range(num_species):
            if output_matrix[i, j] > 0.5:
                coef = int(output_matrix[i, j]) if output_matrix[i, j] > 1 else ''
                products.append(f"{coef}s{row_mapping[i] + 1}")
        
        # Construct reaction string
        reactant_str = ' + '.join(reactants) if reactants else ''
        product_str = ' + '.join(products) if products else ''
        reaction = f"{reactant_str} -> {product_str} {x[column_mapping[j]]}"
        reactions.append(reaction + '\n')
    
    return reactions
# =============================================================================


# =============================================================================
def recordReactionsNamesSpecies(output_matrix, input_matrix, x, row_mapping, column_mapping, name_species):
    """
    Generate string representations of chemical reactions using species names.

    Parameters:
    - output_matrix (np.ndarray): Output stoichiometric matrix.
    - input_matrix (np.ndarray): Input stoichiometric matrix.
    - x (np.ndarray): Reaction flows.
    - row_mapping (dict): Mapping for species indices.
    - column_mapping (dict): Mapping for reaction indices.
    - name_species (list): List of species names.

    Returns:
    - List[str]: List of reaction strings with species names.
    """
    num_species, num_reactions = input_matrix.shape
    reactions = []

    for j in range(num_reactions):
        reactants = []
        products = []
        
        # Gather reactants
        for i in range(num_species):
            if input_matrix[i, j] > 0.5:
                coef = int(input_matrix[i, j]) if input_matrix[i, j] > 1 else ''
                reactants.append(f"{coef}{name_species[row_mapping[i]]}")
        
        # Gather products
        for i in range(num_species):
            if output_matrix[i, j] > 0.5:
                coef = int(output_matrix[i, j]) if output_matrix[i, j] > 1 else ''
                products.append(f"{coef}{name_species[row_mapping[i]]}")
        
        # Construct reaction string
        reactant_str = ' + '.join(reactants) if reactants else ''
        product_str = ' + '.join(products) if products else ''
        reaction = f"{reactant_str} -> {product_str} {x[column_mapping[j]]}"
        reactions.append(reaction + '\n')
    
    return reactions
# =============================================================================









