# -*- coding: utf-8 -*-
"""
Created on Thu Dec 26 01:52:02 2024

@author: Trabajador
"""

import networkx as nx
import numpy as np
import gurobipy as gb
import time
from typing import Any
import auxiliary_functions as aux


# =============================================================================
def removeNullRowsAndColumns(matrix1, matrix2, tolerance=1e-10):
    """
    Remove rows and columns from two matrices where all elements are below a tolerance in either matrix.

    Parameters:
    - matrix1, matrix2 (np.ndarray): Input matrices to be modified.
    - tolerance (float): Threshold below which elements are considered zero.

    Returns:
    - Tuple[np.ndarray, np.ndarray, List[int], List[int]]: 
        Modified matrices, removed row indices, removed column indices.

    Raises:
    - ValueError: If matrices do not have the same dimensions or if index tracking fails.
    """
    # Check if the matrices have the same dimensions
    if matrix1.shape != matrix2.shape:
        raise ValueError("Both matrices must have the same dimensions")

    # Original list of rows and columns
    original_rows = np.arange(matrix1.shape[0]) 
    original_columns = np.arange(matrix1.shape[1])

    # Initialize lists to store indices of null rows and columns
    rows_removed = []
    columns_removed = []
    
    # Initialize lists of indices of rows and columns that are kept in the solution
    rows_kept = np.arange(matrix1.shape[0]) 
    columns_kept = np.arange(matrix1.shape[1])
        
    while True:

        null_rows = []
        null_columns = []
        
        rows_to_remove = []
        columns_to_remove = []

        # Check for null rows in either matrix
        for idx, value in enumerate(rows_kept):
            if (np.all(np.abs(matrix1[idx, :]) < tolerance) 
                or np.all(np.abs(matrix2[idx, :]) < tolerance)):
                null_rows.append(value)
                rows_to_remove.append(idx)

        # Check for null columns in either matrix
        for idx, value in enumerate(columns_kept):
            if (np.all(np.abs(matrix1[:, idx]) < tolerance) 
                or np.all(np.abs(matrix2[:, idx]) < tolerance)):
                print()
                null_columns.append(value)
                columns_to_remove.append(idx)

        # If no new null rows or columns are found, exit the loop
        if not null_rows and not null_columns:
            break
        
        # Update the lists of rows and columns removed
        rows_removed.extend(null_rows)
        columns_removed.extend(null_columns)
        
        # Update the lists of rows and columns kept
        rows_kept = sorted(list(set(rows_kept) - set(null_rows)))
        columns_kept = sorted(list(set(columns_kept) - set(null_columns)))

        # Remove null rows and columns from both matrices
        matrix1 = np.delete(matrix1, rows_to_remove, axis = 0)  # Remove null rows
        matrix1 = np.delete(matrix1, columns_to_remove, axis = 1)  # Remove null columns

        matrix2 = np.delete(matrix2, rows_to_remove, axis = 0)  # Remove null rows
        matrix2 = np.delete(matrix2, columns_to_remove, axis = 1)  # Remove null columns
    
    # Verify that the final lists of rows and columns match the original dimensions
    total_rows = list(rows_kept) + list(rows_removed)
    total_rows.sort()
    total_columns = list(columns_kept) + list(columns_removed)
    total_columns.sort()
    # Check if the lists of rows and columns are identical to the original indices
    check_rows = all(x == y for x, y in zip(original_rows, total_rows))
    check_columns = all(x == y for x, y in zip(original_columns, total_columns))
    if not check_rows:
        raise ValueError("Error: Row indices do not match the original matrix.")
    if not check_columns:
        raise ValueError("Error: Column indices do not match the original matrix.")

    return matrix1, matrix2, sorted(rows_removed), sorted(columns_removed)
# =============================================================================


# =============================================================================
def mappingRowsAndColumns(matrix, rows_to_remove, columns_to_remove):
    """
    Generate mappings for row and column indices after removing specified rows and columns.
    
    Parameters:
    - matrix (np.ndarray): The original matrix.
    - rows_to_remove (list): Indices of rows to be removed.
    - columns_to_remove (list): Indices of columns to be removed.
    
    Returns:
    - Tuple[dict, dict]: 
        - row_mapping: Maps new row indices to old row indices.
        - column_mapping: Maps new column indices to old column indices.
    """
    # Create the row mapping from old row indices to new row indices
    # -----------
    row_mapping = {}
    current_row = 0
    for old_row in range(matrix.shape[0]):
        if old_row not in rows_to_remove:
            row_mapping[old_row] = current_row
            current_row += 1
    # Reverse the row mapping: new_row -> old_row
    row_mapping = {new_row: old_row 
                      for old_row, new_row in row_mapping.items()}
    # -----------

    # Create the column mapping from old column indices to new column indices
    # -----------
    column_mapping = {}
    current_column = 0
    for old_column in range(matrix.shape[1]):
        if old_column not in columns_to_remove:
            column_mapping[old_column] = current_column
            current_column += 1
    # Reverse the row mapping: new_row -> old_row
    column_mapping = {new_column: old_column 
                         for old_column, new_column in column_mapping.items()}
    # -----------
    return row_mapping, column_mapping
# =============================================================================


# =============================================================================
def giveMeMatrixByComponent(input_matrix, output_matrix):
    """
    Construct a bipartite graph from input and output matrices and decompose it into weakly connected components.
    
    Parameters:
    - input_matrix (np.ndarray): Matrix representing reactant coefficients.
    - output_matrix (np.ndarray): Matrix representing product coefficients.
    
    Returns:
    - List[dict]: Each dict represents a component with keys for input and output matrices, 
      species indices, and reaction indices.
    """
    # Create the graph
    G = nx.DiGraph()
    
    # Get the number of species and reactions
    num_species, num_reactions = input_matrix.shape
    
    # Add species nodes
    for i in range(num_species):
        G.add_node(f'Species_{i+1}', bipartite=0)
    
    # Add reaction nodes
    for j in range(num_reactions):
        G.add_node(f'Reaction_{j+1}', bipartite=1)
    
    # Add edges from species to reactions (input matrix)
    for i in range(num_species):
        for j in range(num_reactions):
            if input_matrix[i, j] > 0:
                G.add_edge(f'Species_{i+1}', f'Reaction_{j+1}')
    
    # Add edges from reactions to species (output matrix)
    for i in range(num_species):
        for j in range(num_reactions):
            if output_matrix[i, j] > 0:
                G.add_edge(f'Reaction_{j+1}', f'Species_{i+1}')
    
    # Find the weakly connected components
    components = list(nx.weakly_connected_components(G))
    
    # Create matrices and mappings for each component
    components_all = []
    for component in components:
        species_indices = []
        reaction_indices = []
    
        for node in component:
            if node.startswith('Species'):
                species_indices.append(int(node.split('_')[1]) - 1)  # Convert to zero-based index
            elif node.startswith('Reaction'):
                reaction_indices.append(int(node.split('_')[1]) - 1)  # Convert to zero-based index
    
        # Create the input and output matrices for this component
        input_submatrix = input_matrix[np.ix_(species_indices, reaction_indices)]
        output_submatrix = output_matrix[np.ix_(species_indices, reaction_indices)]
    
        # Store the submatrices and mappings
        components_all.append({'input': input_submatrix, 'output': output_submatrix, 'species': species_indices, 'reactions': reaction_indices})

    return components_all
# =============================================================================


# =========================================================================
def recordReactionsAltered(output_matrix, input_matrix, x, row_mapping, column_mapping, column_mapping_alter):
    """
    Generate string representations of chemical reactions.

    Parameters:
    - output_matrix (np.ndarray): Output stoichiometric matrix.
    - input_matrix (np.ndarray): Input stoichiometric matrix.
    - x (np.ndarray): Reaction flows.
    - row_mapping (dict): Mapping from old species indices to new indices for string representation.
    - column_mapping (dict): Mapping from old reaction indices to new indices (unused in this function).
    - column_mapping_alter (dict): Alternative mapping for reaction indices for flow annotation.

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
        reaction = f"{reactant_str} -> {product_str} {x[column_mapping_alter[j]]}"
        reactions.append(reaction + '\n')

    return reactions
# =========================================================================


# =========================================================================
def recordReactionsAlteredWithNames(output_matrix, input_matrix, x, row_mapping, column_mapping, column_mapping_alter, name_species):
    """
    Generate string representations of chemical reactions with species names.

    Parameters:
    - output_matrix (np.ndarray): Output stoichiometric matrix.
    - input_matrix (np.ndarray): Input stoichiometric matrix.
    - x (np.ndarray): Reaction flows.
    - row_mapping (dict): Mapping from old species indices to new indices for string representation.
    - column_mapping (dict): Mapping from old reaction indices to new indices (unused in this function).
    - column_mapping_alter (dict): Alternative mapping for reaction indices for flow annotation.
    - name_species (list): Names of species for reaction representation.

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
        reaction = f"{reactant_str} -> {product_str} {x[column_mapping_alter[j]]}"
        reactions.append(reaction + '\n')

    return reactions
# =============================================================================


# =============================================================================
def growthRateInSubgraphDefinitive(
        input_matrix: Any,
        output_matrix: Any,
        scenario_name: str,
        time_limit_iteration: int,
        name_species = ""
    ) -> None:
    """
    Calculate the growth rate of subgraphs and log the results to a file.

    Args:
        input_matrix: Matrix of input reactions.
        output_matrix: Matrix of output reactions.
        scenario_name: Name for the output file.
        time_limit_iteration: Time limit for each algorithm iteration.
    """
    
    # Constants
    MAX_STEPS = 1000
    NULL_THRESHOLD = 0.1  # Threshold for determining null rows/columns
    
    # Preprocessing: Remove null rows and columns
    try:
        input_modified, output_modified, null_rows, null_columns = removeNullRowsAndColumns(
            input_matrix, output_matrix, NULL_THRESHOLD
        )
    except Exception as e:
        raise RuntimeError(f"Error in preprocessing matrices: {e}")
    
    # Mapping rows and columns
    row_mapping, column_mapping = mappingRowsAndColumns(input_matrix, null_rows, null_columns)
    
    # Decompose into independent components
    components = giveMeMatrixByComponent(input_modified, output_modified)
    
    # Create a list of component dictionaries
    component_dicts = [
        {
            "input": comp["input"],
            "output": comp["output"],
            "species": [row_mapping[idx] for idx in comp["species"]],
            "reactions": [column_mapping[idx] for idx in comp["reactions"]],
        }
        for comp in components
    ]
    
    # Solve for each component
    solutions = []
    for component in component_dicts:
        try:
            solution = growthRateinSubgraph(
                component["output"], component["input"], MAX_STEPS, time_limit_iteration
            )
        except Exception as e:
            raise RuntimeError(f"Error in solving subgraph: {e}")
        
        solutions.append({
            "x": solution[0],
            "alpha": solution[1],
            "step": solution[2],
            "alphaDict": solution[3],
            "a": solution[4],
            "z": solution[5],
            "time": solution[6],
            "species": component["species"],
            "reactions": component["reactions"],
            "dict_sol": solution[7],
        })
    
    # Find the solution with the maximum growth factor (alpha)
    best_solution = max(solutions, key=lambda sol: sol["alpha"])
    
    # Prepare output data
    output_lines = []
    output_lines.append(f"{solutions}\n")
    output_lines.append(f"Total time:\n{best_solution['time']}\n")
    output_lines.append(f"S dimension:\n{input_matrix.shape}\n")
    output_lines.append(f"Autonomy S:\n{aux.checkAutonomy(input_matrix, output_matrix)[2]}\n")
    output_lines.append(f"Number of autocatalytic species (a):\n{len(best_solution['a'])}\n")
    output_lines.append(
        f"Autocatalytic species (a):\n{' '.join(['s' + str(best_solution['species'][i] + 1) for i in best_solution['a']])}\n"
    )
    output_lines.append(f"species (numbers):\n{[best_solution['species'][i] for i in best_solution['a']]}\n")
    output_lines.append(f"reactions (numbers):\n{[best_solution['reactions'][z] for z in best_solution['z']]}\n")
    output_lines.append(f"Growth factor:\n{best_solution['alpha']}\n")
    
    # Record the resulting reactions
    selected_reactions = [best_solution["reactions"][z] for z in best_solution["z"]]
    output_ssp = output_matrix[:, selected_reactions]
    output_ssm = input_matrix[:, selected_reactions]
    
    # Map the rows and columns for the final output
    new_column_mapping = {i: selected_reactions[i] for i in range(len(selected_reactions))}
    alter_column_mapping = {i: best_solution["z"][i] for i in range(len(best_solution["z"]))}
    row_mapping = {i: i for i in range(output_ssm.shape[0])}
        
    if name_species == "":
        reaction_details = recordReactionsAltered(output_ssp, output_ssm, best_solution["x"], row_mapping, new_column_mapping, alter_column_mapping)
    else:
        reaction_details = recordReactionsAlteredWithNames(output_ssp, output_ssm, best_solution["x"], row_mapping, new_column_mapping, alter_column_mapping, name_species)

    output_lines.append("S_result reactions:\n")
    output_lines.extend(reaction_details)
    
    # Write output to a file
    output_file = f"output\{scenario_name}_algorithm_3.txt"
    try:
        with open(output_file, 'w') as f:
            f.writelines(output_lines)
    except Exception as e:
        raise RuntimeError(f"Error writing to file {output_file}: {e}")
# =============================================================================


# =============================================================================
def growthRateinSubgraph(output_matrix, input_matrix, t_max, time_limit_iteration):
    """
    Calculate the growth rate for a chemical reaction network in a subgraph.
    
    Parameters:
    - output_matrix (np.ndarray): Matrix representing reaction products.
    - input_matrix (np.ndarray): Matrix representing reaction reactants.
    - t_max (int): Maximum number of iterations for convergence.
    - time_limit_iteration (float): Time limit for each optimization step in seconds.
    
    Returns:
    - Tuple[np.ndarray, float, int, dict, list, list, float, dict]: 
        (optimal_flows, final_growth_rate, steps, growth_rates, active_species, active_reactions, total_time, iteration_data)
    """
    # Parameters
    # ---------------------------
    # Number Species (int) and Number Reactions (int)
    num_species, num_reactions = output_matrix.shape
    # Species (list)
    species = range(num_species)
    # Reactions (list)
    reactions = range(num_reactions)
    # Alpha_0 (float)
    x_0 = np.ones(num_reactions)
    #
    alpha_0 = np.min([sum(output_matrix[s, r] * x_0[r] 
                          for r in reactions)
                      /
                      sum(input_matrix[s, r] * x_0[r] 
                          for r in reactions) 
                      for s in species])
    #
    if alpha_0 < 0.001:
        x_0 = np.random.randint(1, 100, size = num_reactions)
        #
        alpha_0 = np.min([sum(output_matrix[s, r] * x_0[r] 
                          for r in reactions)
                      /
                      sum(input_matrix[s, r] * x_0[r] 
                          for r in reactions) 
                      for s in species])
    # --------------------------------------
    # -------------------------------------------------------------------------
    def modelGrowthRateFixed(alpha_0, time_limit_iteration):
        """
        Set up and solve an optimization problem to determine the growth rate in a chemical reaction network.
    
        Parameters:
        - alpha0 (float): Previous growth rate estimate.
        - time_limit_iteration (float): Time limit for this optimization step in seconds.
        - output_matrix (np.ndarray): Matrix of output coefficients for reactions.
        - input_matrix (np.ndarray): Matrix of input coefficients for reactions.
        - number_species (int): Number of species in the system.
        - number_reactions (int): Number of reactions in the system.
    
        Returns:
        - Tuple[np.ndarray, float, list, list, float, int, int]: 
            (optimal_flows, optimal_growth_rate, active_species, active_reactions, MIP gap, number of variables, number of constraints)
        """
        # Parameters
        upper_bound = 1000
        bigM2 = upper_bound  # Big-M for constraint relaxation
    
        # Initialize model
        model = gb.Model("Growth_Rate_Model_SN")
        model.Params.OutputFlag = 0  # Suppress console output
        model.Params.TimeLimit = time_limit_iteration
        model.Params.MIPGap = 0.00  # Set to zero for exact solutions, might be too strict for practical use
    
        # Define variables
        flows = model.addVars(num_reactions, lb=0, ub=upper_bound, name="reaction_flows")
        growth_rate = model.addVar(name="growth_rate")
        is_autocatalytic = model.addVars(num_species, vtype=gb.GRB.BINARY, name="is_autocatalytic")
        is_active_reaction = model.addVars(num_reactions, vtype=gb.GRB.BINARY, name="is_active_reaction")

        # Objective function
        model.setObjective(growth_rate, gb.GRB.MAXIMIZE)
        # Constraints
        # --------------------------------------
        model.addConstrs(
            (
            growth_rate <= gb.quicksum(output_matrix[s, r] * flows[r] 
                                  for r in reactions)
                    - alpha_0 * gb.quicksum(input_matrix[s, r] * flows[r]
                                            for r in reactions) 
                    + alpha_0*sum(input_matrix[s,:])*upper_bound*(1 - is_autocatalytic[s])
                    for s in species),
            name = "name1")
        #
        model.addConstrs(
            (gb.quicksum(input_matrix[s, r] * flows[r] 
                          for r in reactions) 
            >= is_autocatalytic[s]
            for s in species 
            if sum(input_matrix[s, :]) > 0),
            name = "name2")
        # #
        #
        model.addConstrs(
            (is_active_reaction[r] <= gb.quicksum(is_autocatalytic[s] for s in species
                                  if output_matrix[s, r] > 0) 
              for r in reactions), 
            name = "name8")
        #
        model.addConstrs(
            (is_active_reaction[r] <= gb.quicksum(is_autocatalytic[s] for s in species 
                                  if input_matrix[s, r] > 0) 
              for r in reactions), 
            name = "name9")
        #
        model.addConstrs(
            (flows[r] <= bigM2 * is_active_reaction[r]
              for r in reactions), 
            name = "name10")
        #
        model.addConstrs(
            (is_active_reaction[r] <= flows[r] 
              for r in reactions), 
            name = "name11")
        #   
        model.addConstr(gb.quicksum(is_autocatalytic[s] 
                                for s in species) >= 1, 
                    name = "name12")
        #
        model.addConstr(gb.quicksum(is_active_reaction[r] 
                                for r in reactions) >= 1,
                    name = "name13")
        # --------------------------------------      
  
        # Solve the model
        model.optimize()
    
        if model.status != gb.GRB.OPTIMAL:
            model.computeIIS()
            model.write("infeasibility_report.ILP")
            print("Model infeasible. Check infeasibility report.")
            raise ValueError("Optimization failed: model is infeasible")
    
        # Extract solution
        optimal_flows = np.array([flows[r].X for r in range(num_reactions)])
        optimal_growth_rate = growth_rate.X
        active_species = [s for s in range(num_species) if is_autocatalytic[s].X > 0.5]
        active_reactions = [r for r in range(num_reactions) if is_active_reaction[r].X > 0.5]
    
        return optimal_flows, optimal_growth_rate, active_species, active_reactions, model.MIPGap, model.NumVars, model.NumConstrs
    # -------------------------------------------------------------------------
        
    stop = False
    step = 0
    alpha_dict = {}
    # alphabar = 10000
    current_alpha = alpha_0
    previous_alpha = 0  # Starting with 0 for comparison
    start_time=time.time()
    
    iteration_data = {}
    
    counter = 1
    while not stop:
        print(counter, current_alpha)
        iteration_start_time = time.time()

        # Solve optimization model for this iteration
        optimal_flows, alpha_bar, active_species, active_reactions, gap, num_vars, num_constrs = modelGrowthRateFixed(current_alpha, time_limit_iteration)
        
        # Update current alpha considering only active species
        current_alpha = np.min([sum(output_matrix[s, r] * optimal_flows[r]
                        for r in reactions)
                        /
                        sum(input_matrix[s, r] * optimal_flows[r] 
                        for r in reactions) 
                    for s in active_species])
        
        counter = counter + 1
        
        iteration_end_time = time.time()
        
        iteration_data[step] = {
            "flows": optimal_flows,
            "active_species": active_species,
            "active_reactions": active_reactions,
            "alpha_bar": alpha_bar,
            "gap": gap,
            "variables": num_vars,
            "constraints": num_constrs,
            "step": step,
            "alpha": current_alpha,
            "time": iteration_end_time - iteration_start_time
        }
        
        if len(active_species) < 1 or np.abs(alpha_bar) < 1e-3 or step >= t_max or np.abs(current_alpha - previous_alpha) < 1e-3:
            stop = True
            alpha_dict[step] = current_alpha
            return optimal_flows, current_alpha, step, alpha_dict, active_species, active_reactions, time.time() - start_time, iteration_data
        else:
            alpha_dict[step] = current_alpha
            previous_alpha = current_alpha
            step += 1
# =============================================================================





















