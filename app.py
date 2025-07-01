import streamlit as st
import pandas as pd
from itertools import product
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="📦 Multi-Box Palletizer with 3D", layout="wide")
st.title(":package: Multi-Box Palletizer with 3D Visualization")

st.markdown("""
Enter up to 10 box types with quantity, dimensions, and horizontal rotation option.
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
3D visualization shows the stacked boxes on the pallet.
""")

# Sidebar pallet settings
st.sidebar.header(":brick: Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)
pallet_base_height = st.sidebar.number_input("Pallet Base Height (cm)", min_value=5.0, value=20.0)
lock_orientation = st.sidebar.checkbox("Lock Orientation (Fix Box Height)", value=False)

# Box input count
box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=3)

# Default input
default_data = [{
    "Part No": f"Part-{i+1}",
    "Length (cm)": 30,
    "Width (cm)": 20,
    "Height (cm)": 15,
    "Quantity": 100,
    "Allow Horizontal Rotation": True
} for i in range(box_count)]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

def calculate_fit_for_box(pallet_L, pallet_W, max_H, box_L, box_W, box_H, qty, allow_horizontal, lock_orient):
    best_fit = 0
    best_layout = None
    if lock_orient:
        orientations = [(box_L, box_W, box_H)]
    else:
        orientations = [(box_L, box_W, box_H)]
        if allow_horizontal:
            orientations.append((box_W, box_L, box_H))

    for orient in orientations:
        l, w, h = orient
        fit_L = int(pallet_L // l)
        fit_W = int(pallet_W // w)
        fit_H = int(max_H // h)
        total_fit = fit_L * fit_W * fit_H
        placed = min(qty, total_fit)
        if placed > best_fit:
            best_fit = placed
            best_layout = {
                "orientation": (l, w, h),
                "fit_L": fit_L,
                "fit_W": fit_W,
                "fit_H": fit_H,
                "placed": placed,
                "height": fit_H * h
            }
    return best_layout, best_fit

def pack_boxes_on_pallets(boxes, pallet_L, pallet_W, max_H, lock_orient):
    pallets = []
    remaining_boxes = boxes.copy()
    while remaining_boxes["Quantity"].sum() > 0:
        pallet = {"boxes": [], "height": 0}
        for idx, row in remaining_boxes.iterrows():
            if row["Quantity"] == 0:
                continue
            layout, max_fit = calculate_fit_for_box(
                pallet_L, pallet_W, max_H,
                row["Length (cm)"], row["Width (cm)"], row["Height (cm)"],
                row["Quantity"], row["Allow Horizontal Rotation"], lock_orient
            )
            if layout is None or layout["placed"] == 0:
                continue
            placed = layout["placed"]
            pallet["boxes"].append({
                "Part No": row["Part No"],
                "Placed": placed,
                "Orientation": layout["orientation"],
                "fit_L": layout["fit_L"],
                "fit_W": layout["fit_W"],
                "fit_H": layout["fit_H"],
                "Box Dimensions (LWH)": layout["orientation"]
            })
            if layout["height"] > pallet["height"]:
                pallet["height"] = layout["height"]
            remaining_boxes.at[idx, "Quantity"] -= placed
        pallets.append(pallet)
        if len(pallets) > 100:
            break
    return pallets, remaining_boxes

def make_cuboid(x, y, z, l, w, h, color, name):
    vertices = np.array([
        [x, y, z], [x+l, y, z], [x+l, y+w, z], [x, y+w, z],
        [x, y, z+h], [x+l, y, z+h], [x+l, y+w, z+h], [x, y+w, z+h]
    ])
    I = [0, 0, 0, 3, 4, 4, 7, 1, 1, 2, 5, 6]
    J = [1, 3, 4, 2, 5, 7, 6, 2, 5, 3, 6, 7]
    K = [3, 2, 5, 6, 7, 3, 2, 5, 6, 7, 7, 4]
    return go.Mesh3d(x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
                     i=I, j=J, k=K, opacity=0.5, color=color, name=name)

def plot_pallet_3d(pallet, pallet_L, pallet_W, pallet_H, pallet_base_H):
    fig = go.Figure()
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'cyan', 'magenta', 'yellow', 'brown', 'pink']
    z_offset = pallet_base_H  # pallet base height
    fig.add_trace(make_cuboid(0, 0, 0, pallet_L, pallet_W, pallet_base_H, 'saddlebrown', 'Pallet Base'))

    for i, box in enumerate(pallet["boxes"]):
        l, w, h = box["Orientation"]
        fit_L, fit_W, fit_H = box["fit_L"], box["fit_W"], box["fit_H"]
        placed = box["Placed"]
        part_no = box["Part No"]
        color = colors[i % len(colors)]

        count = 0
        for z in range(fit_H):
            for y in range(fit_W):
                for x in range(fit_L):
                    if count >= placed:
                        break
                    x_pos = (pallet_L - fit_L * l) / 2 + x * l
                    y_pos = (pallet_W - fit_W * w) / 2 + y * w
                    z_pos = z * h + z_offset
                    fig.add_trace(make_cuboid(x_pos, y_pos, z_pos, l, w, h, color, part_no))
                    count += 1

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Length (cm)', range=[0, pallet_L]),
            yaxis=dict(title='Width (cm)', range=[0, pallet_W]),
            zaxis=dict(title='Height (cm)', range=[0, pallet_H]),
            aspectmode='data'
        ),
        height=700,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    return fig

def get_used_pallet_dimensions(pallet, pallet_L, pallet_W, pallet_base_height):
    max_x = 0
    max_y = 0
    max_z = 0
    for box in pallet["boxes"]:
        l, w, h = box["Orientation"]
        fit_L, fit_W, fit_H = box["fit_L"], box["fit_W"], box["fit_H"]
        placed = box["Placed"]

        count = 0
        for z in range(fit_H):
            for y in range(fit_W):
                for x in range(fit_L):
                    if count >= placed:
                        break
                    x_pos = (pallet_L - fit_L * l) / 2 + x * l
                    y_pos = (pallet_W - fit_W * w) / 2 + y * w
                    z_pos = z * h + pallet_base_height
                    max_x = max(max_x, x_pos + l)
                    max_y = max(max_y, y_pos + w)
                    max_z = max(max_z, z_pos + h)
                    count += 1

    return max_x, max_y, max_z - pallet_base_height  # cargo height only

if st.button(":mag: Calculate Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets, remaining = pack_boxes_on_pallets(boxes, pallet_length, pallet_width, max_pallet_height, lock_orientation)
        st.success(f"Total pallets needed: {len(pallets)}")

        st.subheader(":straight_ruler: Pallet Size")
        st.write(f"Input Pallet Dimensions — Length: {pallet_length} cm, Width: {pallet_width} cm, Height: {max_pallet_height} cm")

        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1} (Stack Height: {pallet['height']:.1f} cm)")
            st.dataframe(pd.DataFrame(pallet["boxes"]))
            st.plotly_chart(plot_pallet_3d(pallet, pallet_length, pallet_width, max_pallet_height, pallet_base_height), use_container_width=True)

            used_L, used_W, cargo_H = get_used_pallet_dimensions(pallet, pallet_length, pallet_width, pallet_base_height)
            total_H = pallet_base_height + cargo_H
            total_L = max(pallet_length, used_L)
            total_W = max(pallet_width, used_W)

            st.write(f"**Total Pallet Dimensions including base:**")
            st.write(f"Length: {total_L:.1f} cm, Width: {total_W:.1f} cm, Height: {total_H:.1f} cm")

        if remaining["Quantity"].sum() > 0:
            st.warning(f"Boxes not placed: {remaining['Quantity'].sum()}")
            st.dataframe(remaining)
