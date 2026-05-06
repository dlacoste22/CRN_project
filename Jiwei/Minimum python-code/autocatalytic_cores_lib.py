# -*- coding: utf-8 -*-
"""
Created on Tue Nov  5 16:15:37 2024

@author: Trabajador
"""

import numpy as np
import gurobipy as gb #for solving the optimization problems
import pandas as pd #to export results to excel files and handle data frames
import time
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy.optimize import curve_fit
from matplotlib.ticker import MaxNLocator
import json


# =============================================================================
def computeMAF(output_matrix, input_matrix, max_steps, time_limit_iteration):
    """
    Calculate MAF and related parameters for a given hypergraph.

    Parameters:
    -----------
    output_matrix : np.ndarray
        The output incidence matrix.
    input_matrix : np.ndarray
        The input incidence matrix.
    max_steps : int
        The maximum number of iterations.
    time_limit_iteration : float
        Time limit for each Gurobi optimization step.

    Returns:
    --------
    x_t : np.ndarray
        Optimal reaction intensities for the final iteration.
    alpha_t : float
        Final calculated amplification factor.
    step : int
        Number of iterations completed.
    alphaDict : dict
        Dictionary of alpha values per iteration.
    total_time : float
        Total computation time.
    results_dict : dict
        Detailed results for each iteration.
    """
    
    # Compute stoichiometric matrix and initial variables
    stoichiometric_matrix = output_matrix - input_matrix
    num_species = stoichiometric_matrix.shape[0]
    num_reactions = stoichiometric_matrix.shape[1]
    x_0 = np.ones(num_reactions)
    
    # Initial MAF estimate (alpha_0)
    initial_alpha_vector = [
        sum(output_matrix[s, r] * x_0[r] for r in range(num_reactions)) /
        max(sum(input_matrix[s, r] * x_0[r] for r in range(num_reactions)), 1e-15)
        for s in range(num_species)
    ]
    alpha_0 = np.min(initial_alpha_vector)
    
    # Inner function for optimizing MAF
    # -------------------------------------------------------------------------
    def computeMAFFixed(previous_alpha, time_limit):
        # Initialize Gurobi model
        m = gb.Model("MAF_Model")
        x = m.addVars(num_reactions, lb=0, ub=1000, name="x")
        alpha = m.addVar(name="alpha")
        
        # Set objective to maximize alpha
        m.setObjective(alpha, gb.GRB.MAXIMIZE)
        
        # Add constraints
        m.addConstrs(
            (alpha <= gb.quicksum(output_matrix[s, r] * x[r] for r in range(num_reactions)) -
             previous_alpha * gb.quicksum(input_matrix[s, r] * x[r] for r in range(num_reactions))
             for s in range(num_species)), name="constraint_MAF")
        
        m.addConstrs(
            (gb.quicksum(input_matrix[s, r] * x[r] for r in range(num_reactions)) >= 1 
             for s in range(num_species)), name="constraint_min_input")
        
        # Set solver parameters
        m.Params.OutputFlag = 0
        m.Params.TimeLimit = time_limit
        
        # Solve model
        m.optimize()
        
        if m.status != gb.GRB.OPTIMAL:
            m.computeIIS()
            m.write("infeasibility_report.ILP")
            print("Model infeasible.")
            return [], 0, [], []
        else:
            xsol = np.array([x[r].x for r in range(num_reactions)])
            alphasol = alpha.x
            return xsol, alphasol, m.NumVars, m.NumConstrs
    # -------------------------------------------------------------------------
    # Initialize variables for iteration
    stop = False
    step = 0
    alphaDict = {0: alpha_0}
    previous_alpha = alpha_0
    alpha_t = alpha_0
    alpha_old = 0
    start_time = time.time()
    results_dict = {}

    # Iterative optimization loop
    while not stop:
        iteration_start_time = time.time()
        
        # Optimize MAF for the current iteration
        x_t, alphabar, num_vars, num_constraints = computeMAFFixed(previous_alpha, time_limit_iteration)
        
        # Calculate new alpha_t
        current_alpha_vector = [
            sum(output_matrix[s, r] * x_t[r] for r in range(num_reactions)) /
            max(sum(input_matrix[s, r] * x_t[r] for r in range(num_reactions)), 1e-15)
            for s in range(num_species)
        ]
        alpha_t = np.min(current_alpha_vector)
        
        # Store iteration details
        results_dict[step] = {
            "x": x_t,
            "alphabar": alphabar,
            "variables": num_vars,
            "constraints": num_constraints,
            "step": step,
            "alpha": alpha_t,
            "time": time.time() - iteration_start_time
        }

        # Convergence check
        if (np.abs(alphabar) < 1e-4 or step > max_steps or np.abs(alpha_old - alpha_t) < 1e-4):
            stop = True
            alphaDict[step] = alpha_t
            total_time = time.time() - start_time
            return x_t, alpha_t, step, alphaDict, total_time, results_dict
        else:
            # Prepare for the next iteration
            alphaDict[step] = alpha_t
            step += 1
            previous_alpha = alpha_t
            alpha_old = alpha_t
# =============================================================================


# =============================================================================
def splitMatrix(matrix):
    """
    Split a matrix into its positive and absolute negative parts.
    
    Parameters:
    - matrix (np.ndarray or array-like): The input matrix to split.
    
    Returns:
    - Tuple[np.ndarray, np.ndarray]: 
        - A matrix with only positive values from the input.
        - A matrix with the absolute values of negative entries from the input, other entries set to zero.
    """
    # Convert the input matrix to a numpy array if it's not already
    matrix = np.array(matrix)

    # Create the positive matrix (keeping positives, setting non-positives to zero)
    positive_matrix = np.where(matrix > 0, matrix, 0)

    # Create the absolute negative matrix (keeping the absolute values of negatives, setting non-negatives to zero)
    abs_negative_matrix = np.where(matrix < 0, -matrix, 0)

    return positive_matrix, abs_negative_matrix
# =============================================================================


# =============================================================================
def histogram(alphas, histogramfile):
    """
    Plot a histogram of MAFs for autocatalytic cores and save to file.
    """
    # create independent figure
    fig, ax = plt.subplots(figsize=(5, 3.5), dpi=150)

    # histogram
    ax.hist(
        alphas,
        bins="auto",          # or fixed like: bins=10
        edgecolor="black",
        alpha=0.8
    )

    # set label
    ax.set_title("Distribution of alphas for Autocatalytic Cores", fontsize=12)
    ax.set_xlabel("Core alphas", fontsize=11)
    ax.set_ylabel("Number of cores", fontsize=11)
    
    # axis
    ax.tick_params(axis="both", labelsize=9)

    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    
    fig.tight_layout()

    # save fig
    fig.savefig(histogramfile, bbox_inches="tight")
    # show fig
    plt.show()

    # close figure
    plt.close(fig)
# =============================================================================

# =============================================================================
def optModelAutocatalyticCores(SM, num_react=0):
    """
    Constructs an optimization model to determine autocatalytic cores based on input and output reaction matrices.
    
    Parameters:
    -----------
    SM : numpy.array
        Stoichiometric matrix, defined as output_matrix - input_matrix.
    num_react : int, optional
        Desired number of reactions in the core. If <= 2, at least two reactions will be enforced (default is 0).
    
    Returns:
    --------
    dict
        Solution dictionary containing the model and variables for species, reactions, fluxes, and reaction supports.
    """

    # Parameters and dimensions
    num_species, num_reactions = SM.shape
    species = range(num_species)
    reactions = range(num_reactions)
    UB = 100  # Large constant for the optimization model

    # Initialize model
    model = gb.Model('ModelCores')

    # Define variables
    # Core species (binary: 1 if species is part of the core, 0 otherwise)
    y = model.addVars(species, vtype=gb.GRB.BINARY, name="y")
    # Species present but not part of the core
    w = model.addVars(species, vtype=gb.GRB.BINARY, name="w")
    # Reaction fluxes, normalized to [0, 1]
    x = model.addVars(reactions, ub=1, name="x")
    # Support of flux vectors (binary: 1 if reaction is part of the support, 0 otherwise)
    z = model.addVars(reactions, vtype=gb.GRB.BINARY, name="z")

    # Production vector: calculates P[i] as the sum of fluxes scaled by stoichiometric matrix
    P = {i: gb.quicksum(SM[i, j] * x[j] for j in reactions) for i in species}

    # Objective function
    # Minimize the number of reactions in the core and a small penalty on the flux
    obj = gb.quicksum(z[j] for j in reactions) + (1 / UB) * gb.quicksum(x[j] for j in reactions)
    model.setObjective(obj, gb.GRB.MINIMIZE)

    # Constraints
    # -----------------------
    # Minimum number of reactions in the core
    if num_react > 2:
        model.addConstr(gb.quicksum(z[j] for j in reactions) == num_react, name="NumReactExact")
    else:
        model.addConstr(gb.quicksum(z[j] for j in reactions) >= 2, name="MinReactions")

    # Enforce support relationship: if x[j] > 0, then z[j] must be 1
    model.addConstrs((x[j] <= z[j] for j in reactions), name="Support")

    # Species constraints: a reaction requires either core or non-core presence of species
    model.addConstrs((y[i] + w[i] >= z[j] for i in species for j in reactions if abs(SM[i, j]) > 0.5), name="SpeciesInReactions")

    # Incompatible reactions (no simultaneous reverse reactions in the core)
    model.addConstrs((z[j] + z[j1] <= 1 for j in reactions for j1 in range(j) if all(SM[:, j1] == -SM[:, j])), name="IncompatibleReactions")

    # Core reaction constraints: core reactions require positive and negative contributions from core species
    model.addConstrs((gb.quicksum(y[i] for i in species if SM[i, j] > 0.5) >= z[j] for j in reactions), name="PosCoreContribution")
    model.addConstrs((gb.quicksum(y[i] for i in species if SM[i, j] < -0.5) >= z[j] for j in reactions), name="NegCoreContribution")

    # If species is core, at least one reaction must have it as both positive and negative
    model.addConstrs((gb.quicksum(z[j] for j in reactions if SM[i, j] > 0.5) >= y[i] for i in species), name="PosReactionForCoreSpecies")
    model.addConstrs((gb.quicksum(z[j] for j in reactions if SM[i, j] < -0.5) >= y[i] for i in species), name="NegReactionForCoreSpecies")

    # If species is non-core present, it must be used by some reaction
    model.addConstrs((gb.quicksum(z[j] for j in reactions if abs(SM[i, j]) > 0.5) >= w[i] for i in species), name="ReactionForNonCoreSpecies")

    # Species exclusivity constraint: species can be either core or non-core, but not both
    model.addConstrs((y[i] + w[i] <= 1 for i in species), name="SpeciesExclusivity")

    # Production constraints for core species with large negative stoichiometric coefficients
    for i in species:
        bigM = sum(-SM[i, j] for j in reactions if SM[i, j] < 0) * UB
        negative_reactions = [j for j in reactions if SM[i, j] < -0.01]
        positive_reactions = [j for j in reactions if SM[i, j] > 0.01]
        if negative_reactions and positive_reactions:
            model.addConstr(P[i] >= 0.001 - bigM * (1 - y[i]), name=f"CoreProduction_{i}")
        else:
            y[i].ub = 0  # Species cannot be core if it has no balancing reactions

    # Core and reaction count consistency: number of core species should match core reactions
    model.addConstr(gb.quicksum(y[i] for i in species) == gb.quicksum(z[j] for j in reactions), name="CoreConsistency")
    # -----------------------

    # Model configuration
    model.Params.OutputFlag = 0
    model.update()

    # Prepare solution dictionary
    solution = {
        "model": model,
        "x": x,
        "y": y,
        "z": z,
        "w": w
    }

    return solution
# =============================================================================


# =============================================================================
def constructDataFrame(species, reactions):
    """
    Construct an empty DataFrame with columns for chemical species and reaction properties.
    
    Parameters:
    - num_species (int): The number of chemical species in the system.
    - num_reactions (int): The number of chemical reactions in the system.
    
    Returns:
    - pd.DataFrame: An empty DataFrame with pre-defined columns.
    
    Columns:
    - AC: Autocatalytic?
    - NumReact: Number of reactions involving this species?
    - Fx: Formation rate of species x?
    - Mx: Mass or Mole fraction of species x?
    - Wx: Weight or another property of species x?
    - EMx: Energy/Mass or some measure for species x?
    - Xy: Flow or rate for reaction y?
    - Zeroes: Count or indicator of zero entries?
    """
    # Define column groups separately for clarity
    ac_column = ["AC"]
    num_react_column = ["NumReact"]
    f_columns = [f"F{i+1}" for i in species]
    m_columns = [f"M{i+1}" for i in species]
    w_columns = [f"W{i+1}" for i in species]
    em_columns = [f"EM{i+1}" for i in species]
    x_columns = [f"X{j+1}" for j in reactions]
    zeroes_column = ["Zeroes"]

    # Concatenate all column groups to form the final column list
    columns = ac_column + num_react_column + f_columns + m_columns + w_columns + em_columns + x_columns + zeroes_column
    
    # Create DataFrame with specified columns
    df = pd.DataFrame(columns=columns)
    
    return df
# =============================================================================
     

# =============================================================================
def printSolution(cnt, SM, Food, Waste, ExtraM, Member, Reactions, Flow, Time, zeros, species, reactions, alpha, txtfile=""):
    """
    Prints and optionally saves to a file the details of a solution for an autocatalytic core model.
    
    Parameters:
    -----------
    cnt : int
        Solution counter.
    SM : numpy.array
        Stoichiometric matrix.
    Food, Waste, ExtraM, Member, Reactions, Flow : lists
        Lists indicating food species, waste species, extra members, core members, reactions, and flows.
    Time : float
        Computation time.
    zeros, species, reactions : list
        Species and reactions names or labels.
    alpha : float
        MAF.
    txtfile : str, optional
        Path to the file for saving the output (default is "", which will print to the console).
    """

    # Determine species and reaction indices
    num_species = SM.shape[0]
    num_reactions = SM.shape[1]
    species_idx = range(num_species)
    reactions_idx = range(num_reactions)

    # Helper function to format reaction details
    # ------------------------------------------------------------------------
    def formatReaction(j):
        reactants = [i for i in species_idx if SM[i, j] <= -0.9]
        products = [i for i in species_idx if SM[i, j] >= 0.9]

        reaction_str = f"{reactions[j]}: "
        # Reactants
        reaction_str += ' + '.join(f"{-SM[i, j]:.0f}{species[i]}" if -SM[i, j] > 1.1 else species[i] for i in reactants)
        reaction_str += " -> "
        # Products
        reaction_str += ' + '.join(f"{SM[i, j]:.0f}{species[i]}" if SM[i, j] > 1.1 else species[i] for i in products)
        return reaction_str
    # ------------------------------------------------------------------------

    # Output list processing function
    # ------------------------------------------------------------------------
    def classifySpecies():
        core_species = [i for i in species_idx if Member[i] > 0.5]
        core_reactions = [j for j in reactions_idx if Reactions[j] > 0.5]
        food, waste, extra = [], [], []

        # Classify species as Food, Waste, or Extra based on reaction roles
        for i in species_idx:
            if i not in core_species and sum(abs(SM[i, j]) for j in core_reactions) > 0.01:
                coeffs = [SM[i, j] for j in core_reactions]
                if all(l < 0.001 for l in coeffs):
                    food.append(i)
                elif all(l > -0.001 for l in coeffs):
                    waste.append(i)
                else:
                    extra.append(i)
        
        return core_species, core_reactions, food, waste, extra
    # ------------------------------------------------------------------------

    # Prepare output lists
    core_species, core_reactions, food, waste, extra = classifySpecies()
    labeled_core_species = [species[i] for i in core_species]
    labeled_food = [species[i] for i in food]
    labeled_waste = [species[i] for i in waste]
    labeled_extra = [species[i] for i in extra]
    labeled_reactions = [reactions[j] for j in core_reactions]
    production = [round(sum(SM[i, j] * Flow[j] for j in reactions_idx), 2) for i in core_species]

    # Define output target
    output = open(txtfile, "a") if txtfile else None

    # Print summary
    # ------------------------------------------------------------------------
    def printSummary():
        output_target = output if output else None
        print(f"**** Solution {cnt}: {sum(Reactions)} reactions", file=output_target)
        print(f"\t #Species: {len(core_species)}, #FoodSet: {len(food)}, #WasteSet: {len(waste)}, "
              f"#ExtraMembersSet: {len(extra)}, #Reactions: {len(core_reactions)}", file=output_target)
        print("\t Food Set:", labeled_food, file=output_target)
        print("\t Waste Set:", labeled_waste, file=output_target)
        print("\t Extra Members in AC:", labeled_extra, file=output_target)
        print("\t Core Species in AC:", labeled_core_species, file=output_target)
        print("\t Reactions in AC:", labeled_reactions, file=output_target)
        print("\t Intensity:", [Flow[j] for j in reactions_idx if Flow[j] > 0.001], "--> Production:", production, file=output_target)
        print("\t MAF:", alpha, file=output_target)
        # Detailed reaction descriptions
        for j in core_reactions:
            print("\t\t", formatReaction(j), file=output_target)
        print(f"\t - CPU Time: {Time:.2f} secs", file=output_target)
    # ------------------------------------------------------------------------

    printSummary()
    # Flush to ensure data is written immediately
    output.flush()

    if output:
        output.close()
# =============================================================================


# =============================================================================
def computeAutocatalyticCores(SM, excelfile: str,  histogramfile: str, txtfile="", names_sp=[], names_re=[], num_react=0):
    """
    Computes autocatalytic cores in a given stoichiometric matrix (SM), 
    with an option to save the output to an Excel and text file.

    Parameters:
    -----------
    SM : numpy.array
        Stoichiometric matrix.
    excelfile : str
        Path to the Excel file where results are saved.
    txtfile : str, optional
        Path to the text file for saving output details.
    names_sp : list, optional
        Names of species.
    names_re : list, optional
        Names of reactions.
    num_react : int, optional
        Number of reactions.
    
    Returns:
    --------
    df : pandas.DataFrame
        Dataframe with computed autocatalytic cores.
    """

    # 0. Initial Parameters
    num_species = SM.shape[0]
    num_reactions = SM.shape[1]
    species_idx = range(num_species)
    reactions_idx = range(num_reactions)

    # 1. Initialize Output DataFrame
    df = constructDataFrame(species_idx, reactions_idx)

    # 2. Optionally, Open Text File and Log Initial Information
    if txtfile:
        with open(txtfile, "w") as f:
            f.write(f"# Species: {num_species}, # Reactions: {num_reactions}\n")
    print(f"# Species: {num_species}, # Reactions: {num_reactions}")
    print("Generating Autocatalytic Cores...")

    # 3. Load Names for Species and Reactions
    species = names_sp if names_sp else [f"C_{i+1}" for i in species_idx]
    if not names_sp:
        species[0] = "C"  # Special case for the first species

    reactions = names_re if names_re else [f"R{j+1}" for j in reactions_idx]

    # 4. Initialize Model
    sol_model = optModelAutocatalyticCores(SM, num_react)
    model = sol_model["model"]
    x, y, z, w = sol_model["x"], sol_model["y"], sol_model["z"], sol_model["w"]

    # Initialize status
    status = gb.GRB.OPTIMAL
    cnt = 0
    total_time = 0
    
    # List MAFs
    alphas = []
    
    list_datos = []
    name_acu = txtfile[:-4] + "_cores.txt"

    with open(name_acu, 'w') as filex:

        # 5. Main Loop - Continue While the Model is Feasible
        while status == gb.GRB.OPTIMAL:
            model.optimize()
            status = model.status
    
            if status == gb.GRB.OPTIMAL:
                # Display progress
                if (cnt + 1) % 5 == 0:
                    print("Autocatalytic Cores:", cnt + 1)
    
                # Extract solution values
                member = [round(y[i].x) for i in species_idx]
                reactions_status = [round(z[j].x) for j in reactions_idx]
                flows = [round(x[j].x, 2) for j in reactions_idx]
    
                # Identify Core Species and Reactions
                core_reactions = [j for j in reactions_idx if z[j].x > 0.5]
                core_species = [i for i in species_idx if y[i].x > 0.5]
                
                # Calculate MAF for each core 
                SM_modified = SM[core_species, :][:, core_reactions]
                output_matrix, input_matrix = splitMatrix(SM_modified)
                max_steps = 1000
                time_limit_iteration = 24*60*60
                sol = computeMAF(output_matrix, input_matrix, max_steps, time_limit_iteration)
                alpha = sol[1]
                alphas.append(alpha)
    
                # Classify Species into Food, Waste, or Extra Member
                food, waste, extra_member = classifySpecies(SM, w, z, species_idx, core_reactions)
    
                especies_totales = []
                for i in core_reactions:
                    vector = SM[:, i]
                    for idx, value in enumerate(vector):
                        if value != 0:
                            especies_totales.append(idx)
                especies_totales = set(especies_totales)
       
    
                dict_datos = {}
                dict_datos["reactions"] = core_reactions
                dict_datos["species"] = core_species
                dict_datos["total_species"] = especies_totales
                dict_datos["food"] = food
                dict_datos["waste"] = waste
                dict_datos["alpha"] = alpha
                list_datos.append(dict_datos)
                

                # Convert the set to a list
                dict_datos['total_species'] = list(dict_datos['total_species'])

                
                # Convert the dictionary to a JSON string
                json_string = json.dumps(dict_datos)
                # Write the JSON string to a new line
                filex.write(json_string + '\n')
                filex.flush()
    
                # Construct Core Stoichiometric Matrix and Count Zeros
                SS = np.empty((sum(member), sum(reactions_status)))
                for j, core_j in enumerate(core_reactions):
                    for i, core_i in enumerate(core_species):
                        SS[i, j] = SM[core_i, core_j]
    
                zero_count = len(core_species) * len(core_species) - np.count_nonzero(SS)
    
                # Update DataFrame with Solution Data
                cnt += 1
                df.loc[cnt - 1] = [cnt] + [len(core_reactions)] + food + member + waste + extra_member + flows + [zero_count]
    
                # Log Time
                time_taken = model.RunTime
                total_time += time_taken
    
                # Print Solution
                printSolution(cnt, SM, food, waste, extra_member, member, reactions_status, flows, time_taken, zero_count, species, reactions, alpha, txtfile=txtfile)
    
                # Update Model Constraints to Prevent Duplicate Solutions
                model.addConstr(gb.quicksum(z[j] for j in reactions_idx if reactions_status[j] > 0.5) <= sum(reactions_status) - 1)

    # 6. Save Results to Excel and Summarize
    df.set_index("AC", inplace=True)
    df.to_excel(excelfile)
    print(f"\n\n# Autocatalytic Cores: {cnt}")
    print(f"Total Computation Time: {total_time:.2f} secs.")
    print(f"Results saved to {excelfile}")
    
    # Plot MAF histogram
    histogram(alphas, histogramfile)
    """
    list_sorted = sorted(list_datos, key=lambda d: d["alpha"])
    
    def findOnesPositions(arr):
        return [index for index, value in enumerate(arr) if value == 1]
    
    new_list_sorted = []
    for i in list_sorted:
        dict_ayuda = {}
        dict_ayuda["species"] = i["species"]
        dict_ayuda["reactions"] = i["reactions"]
        dict_ayuda["food"] = findOnesPositions(i["food"])
        dict_ayuda["waste"] = findOnesPositions(i["waste"])
        dict_ayuda["alpha"] = i["alpha"]
        new_list_sorted.append(dict_ayuda)
        
    plotMAFs(list_sorted)
    """
    return df
# =============================================================================


# =============================================================================
def classifySpecies(SM, w, z, species_idx, core_reactions):
    """
    Classify species into food, waste, and extra members based on reaction matrix.

    Parameters:
    -----------
    SM : numpy.array
        Stoichiometric matrix.
    w : gurobipy variable
        Species type indicator.
    z : gurobipy variable
        Reaction indicator.
    species_idx : range
        Indices of species.
    core_reactions : list
        List of core reactions.

    Returns:
    --------
    food, waste, extra_member : list
        Lists indicating whether each species is classified as food, waste, or extra.
    """
    num_species = len(species_idx)
    food, waste, extra_member = [0] * num_species, [0] * num_species, [0] * num_species

    for i in species_idx:
        if w[i].x > 0.5:
            coefficients = [SM[i, j] for j in core_reactions]
            if all(c < 0.001 for c in coefficients):
                food[i] = 1
            elif all(c > -0.001 for c in coefficients):
                waste[i] = 1
            else:
                extra_member[i] = 1

    return food, waste, extra_member
# =============================================================================


# =============================================================================
def plotMAFs(networks):
    """
    Plot MAF compared to the number of reactions and species in a single plot, 
    overlaying the data with mean MAFs and a quadratic model for both cases. 
    Uses different scales on the x-axis, with one going left-to-right and the other right-to-left.

    Parameters:
        networks (list of dict): List of dictionaries where each dictionary 
        contains keys: 'total_species', 'reactions', and 'alpha' (MAF).
    """
    
    # ------------------------------------------------
    def quadratic_model(x, a, b, c):
        """Quadratic model: y = ax^2 + bx + c"""
        x = np.array(x)  # Ensure NumPy array
        return a * x**2 + b * x + c
    # ------------------------------------------------
    
    # Extracting data from the list of dictionaries
    species_counts = [len(network['total_species']) for network in networks]
    reaction_counts = [len(network['reactions']) for network in networks]
    growth_factors = [network['alpha'] for network in networks]
        
    # Calculate mean growth factors for each unique number of reactions
    reactions_to_growth = defaultdict(list)
    for reactions, growth in zip(reaction_counts, growth_factors):
        reactions_to_growth[reactions].append(growth)
    mean_growth_reactions = {r: np.mean(gf) for r, gf in reactions_to_growth.items()}
    # Prepare data for fitting
    reaction_fit_x = np.array(sorted(set(len(network['reactions']) for network in networks)))
    growth_factors_by_reactions = [np.mean([gf for rx, gf in zip(reaction_counts, growth_factors) if rx == r]) for r in reaction_fit_x]
    # Fit the model
    popt_reactions, _ = curve_fit(quadratic_model, reaction_fit_x, growth_factors_by_reactions)
    
    # Calculate mean growth factors for each unique number of species
    species_to_growth = defaultdict(list)
    for species, growth in zip(species_counts, growth_factors):
        species_to_growth[species].append(growth)
    mean_growth_species = {s: np.mean(gf) for s, gf in species_to_growth.items()}
    # Prepare data for fitting
    specie_fit_x = np.array(sorted(set(len(network['total_species']) for network in networks)))
    growth_factors_by_species = [np.mean([gf for rx, gf in zip(species_counts, growth_factors) if rx == r]) for r in specie_fit_x]
    # Fit the model
    popt_species, _ = curve_fit(quadratic_model, specie_fit_x, growth_factors_by_species)
    
    # Create a single plot with twin axes
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # First axis (left-to-right): Growth Factor vs. Number of Reactions
    ax1.scatter(reaction_counts, growth_factors, color='royalblue', s=100, edgecolor='k', alpha=0.7, label='Reactions: Individual Points')
    ax1.plot(sorted(mean_growth_reactions.keys()), 
             [mean_growth_reactions[r] for r in sorted(mean_growth_reactions.keys())], 
             color='royalblue', marker='o', linewidth=2, label='Reactions: Mean MAF')
    ax1.plot(reaction_fit_x, quadratic_model(reaction_fit_x, *popt_reactions), 
             label='Reactions: Quadratic Fit', color='royalblue', linestyle='--', linewidth=2)
    ax1.set_xlabel('Number of Reactions (left-to-right)', color='royalblue', fontsize='large')
    ax1.set_ylabel('MAF', fontsize='large')
    ax1.tick_params(axis='x', colors='royalblue', labelsize=12)
    ax1.tick_params(axis='y', labelsize=12)  # Increase y-axis tick size

    # Second axis (right-to-left): Growth Factor vs. Number of Species
    ax2 = ax1.twiny()  # Create a twin axis sharing the y-axis
    ax2.scatter(species_counts, growth_factors, color='orangered', s=100, edgecolor='k', alpha=0.7, label='Species: Individual Points')
    ax2.plot(sorted(mean_growth_species.keys()), 
             [mean_growth_species[s] for s in sorted(mean_growth_species.keys())], 
             color='orangered', marker='o', linewidth=2, label='Species: Mean MAF')
    ax2.plot(specie_fit_x, quadratic_model(specie_fit_x, *popt_species), 
             label='Species: Quadratic Fit', color='orangered', linestyle='--', linewidth=2)
    ax2.set_xlabel('Number of Species (right-to-left)', color='orangered', fontsize='large')
    ax2.xaxis.set_ticks_position('top')  # Place the x-axis on top
    ax2.xaxis.set_label_position('top')  # Label position
    ax2.invert_xaxis()  # Reverse the direction of the x-axis
    ax2.tick_params(axis='x', colors='orangered', labelsize=12)
    
    # Add legends for clarity
    ax1.legend(loc='upper left', bbox_to_anchor=(0, 1.15), fontsize='large')
    ax2.legend(loc='upper right', bbox_to_anchor=(1, 1.15), fontsize='large')
    
    # Adjust layout
    plt.title('MAF vs. Number of Reactions and Species')
    plt.tight_layout()
    plt.show()
# =============================================================================
    
# =============================================================================
def saveDictionariesToFile(dictionaries, filename):
    """
    Save each dictionary from a list into a new line in a text file.
    
    Parameters:
        dictionaries (list of dict): List of dictionaries to save.
        filename (str): Name of the file to save the data.
    """
    with open(filename, 'w') as file:
        for dictionary in dictionaries:
            # Convert the dictionary to a JSON string
            json_string = json.dumps(dictionary)
            # Write the JSON string to a new line
            file.write(json_string + '\n')
# =============================================================================
