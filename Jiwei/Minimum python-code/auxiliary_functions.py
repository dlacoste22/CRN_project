# -*- coding: utf-8 -*-
"""
Created on Sat Dec 28 23:56:52 2024

@author: Trabajador
"""
import numpy as np
import os
from typing import Tuple

# =============================================================================
def readScenario(name: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Read input and output matrices for a given scenario from files.

    Parameters:
    - name (str): The name of the scenario without file extensions.

    Returns:
    - Tuple[np.ndarray, np.ndarray]: A tuple containing the input (mMinus) and output (mPlus) matrices.

    Raises:
    - FileNotFoundError: If either file cannot be found.
    - ValueError: If matrices read do not have the same dimensions.
    """
    base_path = "./scenarios/"
    
    # Construct file paths using os.path for better cross-platform compatibility
    minus_file = os.path.join(base_path, f"{name}_minus.txt")
    plus_file = os.path.join(base_path, f"{name}_plus.txt")

    # Use try-except for error handling
    try:
        # Read matrices with error checking for file existence
        m_minus = np.loadtxt(minus_file, dtype=int)
        m_plus = np.loadtxt(plus_file, dtype=int)
        
        # Check if matrices have the same dimension
        if m_minus.shape != m_plus.shape:
            raise ValueError(f"Matrices from {name} have different dimensions: {m_minus.shape} vs {m_plus.shape}")
        
        return m_minus, m_plus

    except FileNotFoundError as e:
        print(f"File not found: {e.filename}")
        raise
    except ValueError as e:
        print(f"Error reading or processing matrix data: {e}")
        raise
# =============================================================================


# =============================================================================
def checkAutonomy(input_matrix, output_matrix, epsilon=1e-7):
    """Check if the network is autonomous."""
    species_autonomy = np.all((np.sum(input_matrix, axis=1) > epsilon) & (np.sum(output_matrix, axis=1) > epsilon))
    reaction_autonomy = np.all((np.sum(input_matrix, axis=0) > epsilon) & (np.sum(output_matrix, axis=0) > epsilon))
    return species_autonomy, reaction_autonomy, species_autonomy and reaction_autonomy
# =============================================================================



