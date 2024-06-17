# Invaders

Theory, scope, example and simulations for this code available here: https://www.overleaf.com/read/cnbmcdmkpdfq#8a848f

The file is Invaders_survival.ipynb, to open with Jupyter Notebook. The code exploits the library made by Praful Gragnani, personally edited by me, to identify cores inside a random network.

The code is organized as follows: 

- Parameters definition: total time, realizations, number of invaders, number of reactions... this part can be edited to generate different examples
- Praful's code calling function and "stoichio" function, to find the cores and compute their eigenvalues when transformed into Metzler
- A function "confusion", to construct the comparing plots: in this cell one can edit where the histogram will be saved
- The main "invasion" function, in here one can change the range of rate constants sample space or the initial conditions for X's and Y's. This function will generate #REALIZATIONS random networks, find the cores in it, check the feedback and the stability, simulate dynamically the evolution of the population with a time series. When this cell is run it will be printed, for each realization, if autocatalysis in present, the eigenvalues for all the cores will be printed next (you can check that there is always one and just one real positive). For each realization, in the "output" folder will be saved a "Stoichio_(realization)" saying if there is autocatalysis, printing the invaders matrix and the whole one, saying if the population survives and printing all the cores. A file "Time_(realization)" will show instead the time evolution of the sum of the population of the invaders for that realization
- The cells below construct the histogram for autocatalyis-surviving and the time series trajectories. These two pictures will be saved in the folder "images" inside "output". In the last cell, is possible to change the range of x and y axis, to have a better view on the trajectories.
