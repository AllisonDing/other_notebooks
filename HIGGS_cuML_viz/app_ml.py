import pandas as pd
from sklearn.preprocessing import StandardScaler
import plotly.express as px
from umap import UMAP
from sklearn.cluster import KMeans
import dash
from dash import dcc, html, Input, Output

# Data Preprocess
colnames = ['label'] + [f'feature_{i}' for i in range(1, 29)]
df = pd.read_csv("HIGGS.csv", names=colnames, nrows = 1_000_000)  # Subsample 1M

# Normalize
X = StandardScaler().fit_transform(df.iloc[:, 1:])

# Run Clustering (UMAP + HDBSCAN)
# Convert data to (GPU-Accelerated) cuDF Pandas DataFrame
df_gpu = pd.DataFrame(X)

# Perform K-Means Clustering using cuML
kmeans = KMeans(n_clusters=5, random_state=42, n_init = 10)
kmeans.fit(df_gpu)

# Get cluster assignments
cluster_labels = kmeans.labels_

# Reduce Dimensionality to 3D using cuML UMAP
umap_2d = UMAP(n_neighbors=15, min_dist=0.1, n_components=2)
embedding_2d = umap_2d.fit_transform(df_gpu)

# Reduce Dimensionality to 3D using cuML UMAP
umap_3d = UMAP(n_neighbors=15, min_dist=0.1, n_components=3)
embedding_3d = umap_3d.fit_transform(df_gpu)

# Combine into a pandas DataFrame
plot_df_2d = pd.DataFrame({
    "UMAP-1": embedding_2d[:, 0],
    "UMAP-2": embedding_2d[:, 1],
    "Cluster": cluster_labels.astype(str)
})

plot_df_3d = pd.DataFrame({
    "UMAP-1": embedding_3d[:, 0],
    "UMAP-2": embedding_3d[:, 1],
    "UMAP-3": embedding_3d[:, 2],
    "Cluster": cluster_labels.astype(str)
})

# Define consistent colors
cluster_colors = {
    "0": "#636EFA",  # Blue
    "1": "#EF553B",  # Red
    "2": "#00CC96",  # Green
    "3": "#AB63FA",  # Purple
    "4": "#FFA15A"  # Orange
}

# Create a Dash application instance
app = dash.Dash(__name__)

# Define the layout of the web app
app.layout = html.Div([
    html.H2("HIGGS Dataset: GPU-Accelerated KMeans + UMAP"),

    # Dropdown to select a specific cluster or view all
    html.Label("Select Cluster:"),
    dcc.Dropdown(
        id='cluster-dropdown',
        options=[{"label": "All", "value": "all"}] + 
                [{"label": f"Cluster {c}", "value": c} for c in sorted(plot_df_2d["Cluster"].unique())],
        value="all",            # default selection
        clearable=False,        # user cannot clear selection to null
        style={"width": "40%"}  # style the dropdown width
    ),

    # Graphs: 2D and 3D scatter plots side-by-side
    html.Div([
        dcc.Graph(id="cluster-scatter-2d"),  # 2D UMAP scatter plot
        dcc.Graph(id="cluster-scatter-3d")   # 3D UMAP scatter plot
    ])
])

# This callback updates both 2D and 3D plots based on dropdown selection
@app.callback(
    Output("cluster-scatter-2d", "figure"),  # Output for 2D plot
    Output("cluster-scatter-3d", "figure"),  # Output for 3D plot
    Input("cluster-dropdown", "value")       # Input from dropdown menu
)

def update_figure(selected_cluster):
    # Filter data based on selected cluster
    if selected_cluster == "all":
        df2d = plot_df_2d
        df3d = plot_df_3d

    else:
        df2d = plot_df_2d[plot_df_2d["Cluster"] == selected_cluster]
        df3d = plot_df_3d[plot_df_3d["Cluster"] == selected_cluster]

    # Create 2D scatter plot using Plotly Express
    fig2d = px.scatter(
        df2d,
        x="UMAP-1",
        y="UMAP-2",
        color="Cluster",
        color_discrete_map=cluster_colors,
        title=f"KMeans Clusters (UMAP 2D) — Showing {'All' if selected_cluster == 'all' else 'Cluster ' + selected_cluster}"
    )

    fig2d.update_traces(marker=dict(size=5))
    fig2d.update_layout(margin=dict(l=0, r=0, b=0, t=40))

    # Create 3D scatter plot using Plotly Express
    fig3d = px.scatter_3d(
        df3d,
        x="UMAP-1",
        y="UMAP-2",
        z="UMAP-3",
        color="Cluster",
        color_discrete_map=cluster_colors,
        title=f"KMeans Clusters (UMAP 3D) — Showing {'All' if selected_cluster == 'all' else 'Cluster ' + selected_cluster}"
    )
    
    fig3d.update_traces(marker=dict(size=5))
    fig3d.update_layout(margin=dict(l=0, r=0, b=0, t=40))
    
    return fig2d, fig3d

# Run the Dash App
if __name__ == "__main__":
    app.run_server(host = '0.0.0.0', debug=True)
