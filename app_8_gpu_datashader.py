import dash
from dash import dcc, Input, Output
import plotly.express as px
import pandas as pd
import datashader as ds
import datashader.transfer_functions as tf
from datashader.utils import export_image
import numpy as np
import colorcet as cc
import dash_mantine_components as dmc
from dash.exceptions import PreventUpdate

# Load a large dataset (or simulate one)
np.random.seed(42)
df = pd.DataFrame({
    "x": np.random.randn(100_000) * 10,
    "y": np.random.randn(100_000) * 10,
    "category": np.random.choice(["A", "B", "C", "D"], 100_000)
})

# Fix: Convert `category` column to categorical type
df["category"] = df["category"].astype("category")

def create_datashader_figure(color_column):
    canvas = ds.Canvas(plot_width=800, plot_height=600)
    
    if df[color_column].dtype.name == "category":
        # If categorical, use count_cat()
        agg = canvas.points(df, 'x', 'y', agg=ds.count_cat(color_column))
        img = tf.shade(agg, color_key={"A": cc.rainbow[0], "B": cc.rainbow[3], "C": cc.rainbow[6], "D": cc.rainbow[9]})
    
    else:
        # If numeric, use mean aggregation
        agg = canvas.points(df, 'x', 'y', agg=ds.mean(color_column))
        img = tf.shade(agg, cmap=cc.fire)  # Use a colormap for numeric values

    img = tf.spread(img, px=2)  # Make it more visually appealing
    return px.imshow(img.to_pil(), title=f"Datashader Visualization ({color_column})")

# Initialize Dash app
app = dash.Dash(__name__)

app.layout = dmc.Container([
    dmc.Title("Plotly Dash + Datashader Interactive Graph", color="blue", size="h3"),

    # Dropdown for selecting attribute to visualize
    dmc.Select(
        label="Choose Color Encoding:",
        id="color-selector",
        data=["category", "x", "y"],  # Add more numerical attributes here
        value="category",
        clearable=False,
        searchable=False
    ),

    # Datashader Graph
    dcc.Graph(id="datashader-graph"),
], fluid=True)

# Callback to update Datashader graph based on user selection
@app.callback(
    Output("datashader-graph", "figure"),
    Input("color-selector", "value")
)

def update_graph(color_column):
    if not color_column:
        raise PreventUpdate
    return create_datashader_figure(color_column)

# Run the app
if __name__ == '__main__':
    app.run(host = '0.0.0.0', debug=True)
