# Setting of the escher map
from escher import Builder

model_file = "./model.json"
map_file = "./map.json"

builder = Builder(
    height=600,
    map_name=None,
    model_json = model_file,
    map_json= map_file)

from cobra.io import load_json_model

cobra_model = load_json_model(filename=model_file)

metabolite_ids = [met.id for met in cobra_model.metabolites]
reaction_ids = [react.id for react in cobra_model.reactions]

from numpy.random import uniform

dict_value_meta = {}
dict_value_flux = {}

for meta in metabolite_ids :
    dict_value_meta[meta] = uniform(0,1)

for react in reaction_ids :
    dict_value_flux[react] = uniform(-1,1)

builder.metabolite_data = dict_value_meta
builder.reaction_data = dict_value_flux


builder.metabolite_scale = [
            { 'type': 'value', 'value': 0.0, 'color': 'rgba(  0,   0,   0, 0.0)', 'size': 20},
            { 'type': 'max'  ,               'color': 'rgba(  0,   0, 255, 1.0)', 'size': 40} ]


builder.reaction_scale = [
            { 'type': 'min',                 'color': 'rgba( 255, 0,   0, 1.0)', 'size': 40},
            { 'type': 'value', 'value': 0.0, 'color': 'rgba( 255, 0, 255, 0.0)', 'size': 10},
            { 'type': 'max',                 'color': 'rgba(   0, 0, 255, 1.0)', 'size': 40}]


import webbrowser
import os

# Exporte la carte en fichier HTML temporaire
html_file = "escher_map.html"
builder.save_html(html_file)

# Ouvre dans le navigateur
webbrowser.open('file://' + os.path.abspath(html_file))