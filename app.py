import streamlit as st
import pandas as pd
import numpy as np
from rectpack import newPacker
import plotly.graph_objects as go

st.set_page_config(page_title="📦 Multi-Box Palletizer with Layer-by-Height 3D Visualization", layout="wide")
st.title(":package: Multi-Box Palletizer with Layer-by-Height 3D Visualization")

st.markdown("""
Enter box types with quantity, dimensions, and horizontal rotation (height fixed).
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
Each layer is packed with only boxes of the same height using a 2D bin packing algorithm, maximizing efficiency and respecting the height constraint.
3D visualization shows the stacked boxes on the pallet.
""")

# Sidebar pallet settings
st.sidebar.header(":brick: Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)
pallet_base_height = st.sidebar.number_input("Pallet Base Height (cm)", min_value=5.0, value=20.0)

box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=6)

default_data = [
    {"Part No": "51700", "Length (cm)": 30, "Width (cm)": 29, "Height (cm)": 60, "Quantity": 14},
    {"Part No": "52363", "Length (cm)": 54, "Width (cm)": 38, "Height (cm)": 31, "Quantity": 5},
    {"Part No": "61385", "Length (cm)": 51, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 78},
    {"Part No": "61386", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 52},
    {"Part No": "61387", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 18},
    {"Part No": "61388", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 52},
]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

def pack_boxes_by_height(boxes, pallet_L, pallet_W, max_H, pallet_base_H):
    pallets = []
    # Group by box height (tallest first)
    for box_height in sorted(boxes["Height (cm)"].unique(), reverse=True):
        group = boxes[boxes["Height (cm)"] == box_height].copy()
        while group["Quantity"].sum() > 0:
            pallet = {"boxes": [], "height": 0, "layers": []}
            z_offset = pallet_base_H
            while z_offset + box_height <= pallet_base_H + max_H and group["Quantity"].sum() > 0:
                # Prepare layer input
                packer = newPacker(rotation=True)
                packer.add_bin(pallet_L, pallet_W)
                rect_indices = []  # Maps rect index to DataFrame index
                for idx, row in group.iterrows():
                    l, w = row["Length (cm)"], row["Width (cm)"]
                    for _ in range(int(row["Quantity"])):
                        packer.add_rect(l, w, len(rect_indices))
                        rect_indices.append(idx)
                packer.pack()
                layer_boxes = []
                used_qty = {}
                for rect in packer.rect_list():
                    x, y, w, h, bin_id, rect_idx = rect
                    df_idx = rect_indices[rect_idx]
                    part_no = group.loc[df_idx, "Part No"]
                    layer_boxes.append({
                        "Part No": part_no,
                        "Position3D": (x, y, z_offset),
                        "Dimensions": (w, h, box_height),
                        "Box Index": df_idx
                    })
                    used_qty[df_idx] = used_qty.get(df_idx, 0) + 1
                if not layer_boxes:
                    # No more boxes fit
                    break
                pallet["layers"].append(layer_boxes)
                pallet["boxes"].extend(layer_boxes)
                for idx, used in used_qty.items():
                    group.loc[idx, "Quantity"] -= used
                pallet["height"] += box_height
                z_offset += box_height
            if pallet["boxes"]:
                pallets.append(pallet)
    return pallets

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
    fig.add_trace(make_cuboid(0, 0, 0, pallet_L, pallet_W, pallet_base_H, 'saddlebrown', 'Pallet Base'))
    for i, box in enumerate(pallet["boxes"]):
        l, w, h = box["Dimensions"]
        x, y, z = box["Position3D"]
        part_no = box["Part No"]
        color = colors[i % len(colors)]
        fig.add_trace(make_cuboid(x, y, z, l, w, h, color, part_no))
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
        l, w, h = box["Dimensions"]
        x, y, z = box["Position3D"]
        max_x = max(max_x, x + l)
        max_y = max(max_y, y + w)
        max_z = max(max_z, z + h)
    return max_x, max_y, max_z - pallet_base_height  # cargo height only

if st.button(":mag: Calculate Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets = pack_boxes_by_height(boxes, pallet_length, pallet_width, max_pallet_height, pallet_base_height)
        st.success(f"Total pallets needed: {len(pallets)}")

        st.subheader(":straight_ruler: Pallet Size")
        st.write(f"Input Pallet Dimensions — Length: {pallet_length} cm, Width: {pallet_width} cm, Height: {max_pallet_height} cm")

        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1} (Stack Height: {pallet['height']:.1f} cm)")
            boxes_table = []
            for box in pallet["boxes"]:
                boxes_table.append({
                    "Part No": box["Part No"],
                    "Position (L,W,H)": box["Position3D"],
                    "Box Dimensions (LWH)": box["Dimensions"]
                })
            st.dataframe(pd.DataFrame(boxes_table))
            fig = plot_pallet_3d(pallet, pallet_length, pallet_width, max_pallet_height, pallet_base_height)
            st.plotly_chart(fig, use_container_width=True, key=f'plotly_chart_{i}')

            used_L, used_W, cargo_H = get_used_pallet_dimensions(pallet, pallet_length, pallet_width, pallet_base_height)
            total_H = pallet_base_height + cargo_H
            total_L = max(pallet_length, used_L)
            total_W = max(pallet_width, used_W)

            st.write(f"**Total Pallet Dimensions including base:**")
            st.write(f"Length: {total_L:.1f} cm, Width: {total_W:.1f} cm, Height: {total_H:.1f} cm")
