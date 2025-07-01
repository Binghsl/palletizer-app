import streamlit as st
import pandas as pd
from itertools import permutations
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="📦 Multi-Box Palletizer with 3D", layout="wide")
st.title("📦 Multi-Box Palletizer with 3D Visualization")

st.markdown("""
Enter up to 10 box types with quantity, dimensions, and rotation option.
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
3D visualization shows the stacked boxes on the pallet.
""")

# Sidebar pallet settings
st.sidebar.header("🧱 Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)

# Box input count
box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=3)

default_data = [{
    "Box Name": f"Box {i+1}",
    "Length (cm)": 30,
    "Width (cm)": 20,
    "Height (cm)": 15,
    "Quantity": 100,
    "Allow Rotation": True
} for i in range(box_count)]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

def calculate_fit_for_box(pallet_L, pallet_W, max_H, box_L, box_W, box_H, qty, allow_rotate):
    best_fit = 0
    best_layout = None

    orientations = permutations((box_L, box_W, box_H)) if allow_rotate else [(box_L, box_W, box_H)]

    for orient in orientations:
        l, w, h = orient
        fit_L = int(pallet_L // l)
        fit_W = int(pallet_W // w)
        fit_H = int(max_H // h)
        total_fit = fit_L * fit_W * fit_H
        placed = min(qty, total_fit)
        if total_fit > best_fit:
            best_fit = total_fit
            best_layout = {
                "orientation": (l, w, h),
                "fit_L": fit_L,
                "fit_W": fit_W,
                "fit_H": fit_H,
                "placed": placed,
                "height": fit_H * h
            }
    return best_layout, best_fit

def pack_boxes_on_pallets(boxes, pallet_L, pallet_W, max_H):
    pallets = []
    remaining_boxes = boxes.copy()

    while remaining_boxes["Quantity"].sum() > 0:
        pallet = {"boxes": [], "height": 0}
        pallet_space_height = max_H
        placed_any = False

        for idx, row in remaining_boxes.iterrows():
            if row["Quantity"] == 0:
                continue

            layout, max_fit = calculate_fit_for_box(
                pallet_L, pallet_W, pallet_space_height,
                row["Length (cm)"], row["Width (cm)"], row["Height (cm)"],
                row["Quantity"], row["Allow Rotation"]
            )
            if layout is None or layout["placed"] == 0:
                continue

            placed = layout["placed"]
            pallet["boxes"].append({
                "Box Name": row["Box Name"],
                "Placed": placed,
                "Orientation": layout["orientation"],
                "Boxes per Layer": layout["fit_L"] * layout["fit_W"],
                "Layers": layout["fit_H"],
                "Box Dimensions (L×W×H)": (row["Length (cm)"], row["Width (cm)"], row["Height (cm)"]),
                "Pallet Layer Height": layout["height"]
            })

            if layout["height"] > pallet["height"]:
                pallet["height"] = layout["height"]

            remaining_boxes.at[idx, "Quantity"] -= placed
            placed_any = True

        if not placed_any:
            st.warning("No more boxes can be placed; stopping to prevent infinite loop.")
            break

        pallets.append(pallet)

        if len(pallets) > 100:
            st.warning("Too many pallets required; stopping calculation.")
            break

    return pallets, remaining_boxes

def make_cuboid(x, y, z, l, w, h, color, name):
    # Create vertices of cuboid at position x,y,z with size l,w,h
    # Return Plotly Mesh3d trace for the cuboid
    vertices = np.array([
        [x, y, z],
        [x + l, y, z],
        [x + l, y + w, z],
        [x, y + w, z],
        [x, y, z + h],
        [x + l, y, z + h],
        [x + l, y + w, z + h],
        [x, y + w, z + h],
    ])

    I = [0, 0, 0, 3, 4, 4, 7, 1, 1, 2, 5, 6]
    J = [1, 3, 4, 2, 5, 7, 6, 2, 5, 3, 6, 7]
    K = [3, 2, 5, 6, 7, 3, 2, 5, 6, 7, 7, 4]

    return go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        color=color,
        opacity=0.5,
        i=I,
        j=J,
        k=K,
        name=name,
        hoverinfo="name"
    )

def plot_pallet_3d(pallet, pallet_L, pallet_W, pallet_H):
    fig = go.Figure()

    # Draw pallet base
    fig.add_trace(go.Mesh3d(
        x=[0, pallet_L, pallet_L, 0, 0, pallet_L, pallet_L, 0],
        y=[0, 0, pallet_W, pallet_W, 0, 0, pallet_W, pallet_W],
        z=[0, 0, 0, 0, 2, 2, 2, 2],  # Pallet thickness 2 cm
        color='saddlebrown',
        opacity=0.7,
        i=[0, 0, 0, 3, 4, 4, 7, 1, 1, 2, 5, 6],
        j=[1, 3, 4, 2, 5, 7, 6, 2, 5, 3, 6, 7],
        k=[3, 2, 5, 6, 7, 3, 2, 5, 6, 7, 7, 4],
        name="Pallet Base",
        hoverinfo="skip"
    ))

    colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'yellow', 'brown', 'pink']

    current_z = 2  # Start stacking above pallet thickness
    for i, box in enumerate(pallet["boxes"]):
        count = box["Placed"]
        l, w, h = box["Orientation"]
        boxes_per_layer = box["Boxes per Layer"]
        layers = box["Layers"]

        # Calculate how many full layers and leftover boxes
        full_layers = count // boxes_per_layer
        leftover = count % boxes_per_layer

        color = colors[i % len(colors)]
        name = box["Box Name"]

        # Position boxes in layers
        for layer in range(full_layers):
            for idx_in_layer in range(boxes_per_layer):
                # Calculate position (simple row-major)
                x_pos = (idx_in_layer % box["Boxes per Layer"]) * l
                y_pos = (idx_in_layer // box["Boxes per Layer"]) * w
                z_pos = current_z + layer * h

                # Check if box fits in pallet bounds - just safety check
                if x_pos + l <= pallet_L and y_pos + w <= pallet_W:
                    fig.add_trace(make_cuboid(x_pos, y_pos, z_pos, l, w, h, color, name))

        # Leftover boxes on next layer
        for idx in range(leftover):
            x_pos = (idx % box["Boxes per Layer"]) * l
            y_pos = (idx // box["Boxes per Layer"]) * w
            z_pos = current_z + full_layers * h
            if x_pos + l <= pallet_L and y_pos + w <= pallet_W:
                fig.add_trace(make_cuboid(x_pos, y_pos, z_pos, l, w, h, color, name))

        current_z += layers * h

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Length (cm)', range=[0, pallet_L]),
            yaxis=dict(title='Width (cm)', range=[0, pallet_W]),
            zaxis=dict(title='Height (cm)', range=[0, pallet_H]),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=700,
        showlegend=True
    )
    return fig

if st.button("🔍 Calculate Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets, remaining = pack_boxes_on_pallets(boxes, pallet_length, pallet_width, max_pallet_height)

        st.success(f"✅ Palletization complete! Total pallets needed: {len(pallets)}")

        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1} (Height: {pallet['height']:.1f} cm)")
            df = pd.DataFrame(pallet["boxes"])
            st.dataframe(df)

            st.plotly_chart(plot_pallet_3d(pallet, pallet_length, pallet_width, max_pallet_height), use_container_width=True)

        if remaining["Quantity"].sum() > 0:
            st.warning(f"⚠️ Remaining boxes not placed: {remaining['Quantity'].sum()}")
            st.dataframe(remaining)

        def pallets_summary_df(pallets):
            data = []
            for i, p in enumerate(pallets):
                for b in p["boxes"]:
                    data.append({
                        "Pallet #": i + 1,
                        "Box Name": b["Box Name"],
                        "Placed": b["Placed"],
                        "Orientation": str(b["Orientation"]),
                        "Boxes per Layer": b["Boxes per Layer"],
                        "Layers": b["Layers"],
                        "Pallet Height (cm)": p["height"]
                    })
            return pd.DataFrame(data)

        summary_df = pallets_summary_df(pallets)
        csv = summary_df.to_csv(index=False)
        st.download_button("⬇️ Download Palletization Summary CSV", csv, "palletization_summary.csv", "text/csv")
