import streamlit as st
import pandas as pd
import numpy as np
from rectpack import newPacker
import plotly.graph_objects as go

st.set_page_config(page_title="📦 Multi-Box Palletizer with 3D", layout="wide")
st.title(":package: Multi-Box Palletizer with 3D Visualization (Iterative Optimized)")

st.markdown("""
Enter up to 10 box types with quantity, dimensions, and horizontal rotation (height fixed).
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
Each layer is packed using a 2D bin packing algorithm, repeatedly, for maximum efficiency.
3D visualization shows the stacked boxes on the pallet.
""")

# Sidebar pallet settings
st.sidebar.header(":brick: Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)
pallet_base_height = st.sidebar.number_input("Pallet Base Height (cm)", min_value=5.0, value=20.0)

box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=3)

default_data = [{
    "Part No": f"Part-{i+1}",
    "Length (cm)": 30,
    "Width (cm)": 20,
    "Height (cm)": 15,
    "Quantity": 100
} for i in range(box_count)]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

def pack_layer_rectpack(boxes, pallet_L, pallet_W):
    packer = newPacker(rotation=True)  # Only horizontal rotation allowed
    packer.add_bin(pallet_L, pallet_W)
    # Add rectangles: (length, width, idx)
    for idx, box in boxes.iterrows():
        l, w = box["Length (cm)"], box["Width (cm)"]
        for _ in range(int(box["Quantity"])):
            packer.add_rect(l, w, idx)
    packer.pack()
    placed = []
    used_qty = {}
    for rect in packer.rect_list():
        x, y, w, h, bin_id, box_idx = rect
        part_no = boxes.at[box_idx, "Part No"]
        box_h = boxes.at[box_idx, "Height (cm)"]
        l = boxes.at[box_idx, "Length (cm)"]
        orig_w = boxes.at[box_idx, "Width (cm)"]
        orientation = (w, h) if (w != l or h != orig_w) else (l, orig_w)
        placed.append({
            "Part No": part_no,
            "Position": (x, y),
            "Dimensions": (w, h, box_h),
            "Orientation": orientation,
            "Box Index": box_idx
        })
        used_qty[box_idx] = used_qty.get(box_idx, 0) + 1
    return placed, used_qty

def pack_boxes_on_pallets_rectpack_iterative(boxes, pallet_L, pallet_W, max_H, pallet_base_H):
    pallets = []
    remaining_boxes = boxes.copy()
    while remaining_boxes["Quantity"].sum() > 0:
        pallet = {"boxes": [], "height": 0, "layers": []}
        z_offset = pallet_base_H
        # Track layer heights for top layer constraint if needed
        layer_index = 0
        while z_offset < pallet_base_H + max_H and remaining_boxes["Quantity"].sum() > 0:
            # Iteratively fill the layer
            layer_boxes = []
            layer_used_qty = {}
            layer_height = None
            # Make a copy of remaining_boxes for this layer iteration
            layer_remaining = remaining_boxes.copy()
            while True:
                placed, used_qty = pack_layer_rectpack(layer_remaining, pallet_L, pallet_W)
                if not placed:
                    break
                # Place boxes at z = z_offset
                for b in placed:
                    b["Position3D"] = (b["Position"][0], b["Position"][1], z_offset)
                layer_boxes.extend(placed)
                # Update layer_remaining for next round
                for idx, used in used_qty.items():
                    layer_remaining.at[idx, "Quantity"] -= used
                    # Track for overall layer
                    layer_used_qty[idx] = layer_used_qty.get(idx, 0) + used
                # If all quantities are zero, end this layer
                if layer_remaining["Quantity"].sum() == 0:
                    break
            if not layer_boxes:
                break
            # All boxes in this layer must have same height (fixed)
            layer_height = max([b["Dimensions"][2] for b in layer_boxes])
            for b in layer_boxes:
                b["Height"] = layer_height
            pallet["layers"].append(layer_boxes)
            pallet["boxes"].extend(layer_boxes)
            # Update remaining_boxes for next layer
            for idx, used in layer_used_qty.items():
                remaining_boxes.at[idx, "Quantity"] -= used
            pallet["height"] += layer_height
            z_offset += layer_height
            layer_index += 1
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
        pallets, remaining = pack_boxes_on_pallets_rectpack_iterative(boxes, pallet_length, pallet_width, max_pallet_height, pallet_base_height)
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

        if remaining["Quantity"].sum() > 0:
            st.warning(f"Boxes not placed: {remaining['Quantity'].sum()}")
            st.dataframe(remaining)
