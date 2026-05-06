import matplotlib.pyplot as plt

# Lire le fichier et extraire la deuxième colonne
with open('growth_factors.txt', 'r') as file:
    lines = file.readlines()

# Extraire les valeurs de la deuxième colonne
values = []
for line in lines:
    columns = line.strip().split()
    if len(columns) >= 2:  # Vérifier qu'il y a au moins deux colonnes
        try:
            value = float(columns[1])  # Convertir en float
            values.append(value)
        except ValueError:
            continue  # Ignorer les lignes où la conversion échoue

# Tracer l'histogramme normalisé
plt.figure(figsize=(10, 6))
plt.hist(values, bins=30, density=True, color='skyblue', edgecolor='black', alpha=0.7)
#plt.title("Histogramme normalisé des valeurs de la deuxième colonne")
#plt.xlabel("Valeurs")
plt.ylabel("Densité")
plt.grid(axis='y', alpha=0.75)

# Sauvegarder la figure dans un fichier PDF
plt.savefig('figure.pdf', format='pdf', bbox_inches='tight')

# Afficher l'histogramme
plt.show()
