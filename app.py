import streamlit as st
import pandas as pd
import numpy as np
from rectpack import newPacker
import io

st.set_page_config(page_title="📦 Efficient Palletizer (Long Side Alignment, Downloadable Packing List)", layout="wide")
st.title(":package: Efficient Palletizer - Long Side Alignment Rule")

st.markdown("""
Enter box types with quantity and dimensions.  
Boxes are packed layer-by-layer on the pallet, with each box's longer side always aligned to the pallet's longer side.  
You can download a single CSV file containing the full pallet packing list.
""")

# --- Sidebar pallet settings ---
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

def align_box_to_pallet(box_length, box_width, pallet_length, pallet_width):
    # Returns (aligned_length, aligned_width)
    if box_length >= box_width:
        box_long_side, box_short_side = box_length, box_width
    else:
        box_long_side, box_short_side = box_width, box_length
    if pallet_length >= pallet_width:
        pallet_long_side, pallet_short_side = pallet_length, pallet_width
    else:
        pallet_long_side, pallet_short_side = pallet_width, pallet_length
    return (pallet_long_side, pallet_short_side) if (box_long_side > box_short_side) else (box_short_side, box_long_side)

def add_box_with_alignment(packer, box_length, box_width, pallet_length, pallet_width, quantity, rect_indices, idx):
    # Align longer side of box with longer side of pallet
    if box_length >= box_width and pallet_length >= pallet_width:
        aligned_length, aligned_width = box_length, box_width
    elif box_length >= box_width and pallet_length < pallet_width:
        aligned_length, aligned_width = box_width, box_length
    elif box_length < box_width and pallet_length >= pallet_width:
        aligned_length, aligned_width = box_width, box_length
    else:
        aligned_length, aligned_width = box_length, box_width
    for _ in range(quantity):
        packer.add_rect(aligned_length, aligned_width, len(rect_indices))
        rect_indices.append(idx)

def pack_boxes_long_side_align(boxes, pallet_L, pallet_W, max_H, pallet_base_H):
    pallets = []
    remaining = boxes.copy()
    # Sort box heights descending for layer packing
    heights_sorted = sorted(remaining["Height (cm)"].unique(), reverse=True)
    while remaining["Quantity"].sum() > 0:
        pallet = {"boxes": [], "height": 0, "layers": []}
        z_offset = pallet_base_H
        for box_height in heights_sorted:
            while z_offset + box_height <= pallet_base_H + max_H and remaining["Quantity"].sum() > 0:
                # Only consider boxes of this height
                layer_boxes_df = remaining[(remaining["Height (cm)"] == box_height) & (remaining["Quantity"] > 0)].copy()
                if layer_boxes_df.empty:
                    break
                packer = newPacker(rotation=False)  # rotation False, alignment applied manually
                packer.add_bin(pallet_L, pallet_W)
                rect_indices = []
                for idx, row in layer_boxes_df.iterrows():
                    add_box_with_alignment(
                        packer,
                        row["Length (cm)"],
                        row["Width (cm)"],
                        pallet_L,
                        pallet_W,
                        int(row["Quantity"]),
                        rect_indices,
                        idx
                    )
                packer.pack()
                layer_boxes = []
                used_qty = {}
                for rect in packer.rect_list():
                    x, y, w, h, bin_id, rect_idx = rect
                    df_idx = rect_indices[rect_idx]
                    part_no = remaining.loc[df_idx, "Part No"]
                    layer_boxes.append({
                        "Part No": part_no,
                        "Position3D": (x, y, z_offset),
                        "Box Length (cm)": w,
                        "Box Width (cm)": h,
                        "Box Height (cm)": box_height,
                        "Layer Z (cm)": z_offset,
                        "Box Index": df_idx
                    })
                    used_qty[df_idx] = used_qty.get(df_idx, 0) + 1
                if not layer_boxes:
                    break
                pallet["layers"].append(layer_boxes)
                pallet["boxes"].extend(layer_boxes)
                for idx, used in used_qty.items():
                    remaining.loc[idx, "Quantity"] -= used
                pallet["height"] += box_height
                z_offset += box_height
        if pallet["boxes"]:
            pallets.append(pallet)
    return pallets

def create_single_csv_packing_list(pallets, pallet_L, pallet_W, max_H):
    # Create a single DataFrame for all pallets
    all_rows = []
    pallet_dims = f"{pallet_L}x{pallet_W}x{max_H} cm"
    for i, pallet in enumerate(pallets):
        for item in pallet["boxes"]:
            all_rows.append({
                "Pallet No": i + 1,
                "Pallet Dimension (cm)": pallet_dims,
                "Part No": item["Part No"],
                "Box Length (cm)": item["Box Length (cm)"],
                "Box Width (cm)": item["Box Width (cm)"],
                "Box Height (cm)": item["Box Height (cm)"],
                "Layer Z (cm)": item["Layer Z (cm)"]
            })
    return pd.DataFrame(all_rows)

if st.button(":mag: Calculate Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets = pack_boxes_long_side_align(boxes, pallet_length, pallet_width, max_pallet_height, pallet_base_height)
        st.success(f"Total pallets needed: {len(pallets)}")

        st.subheader(":straight_ruler: Pallet Dimensions")
        st.write(f"Pallet dimensions: {pallet_length} × {pallet_width} × {max_pallet_height} cm")

        # All pallets in one CSV
        single_df = create_single_csv_packing_list(pallets, pallet_length, pallet_width, max_pallet_height)
        st.download_button(
            label="⬇️ Download FULL packing list (all pallets in one CSV)",
            data=single_df.to_csv(index=False).encode("utf-8"),
            file_name="all_pallets_packing_list.csv",
            mime="text/csv"
        )

        # Show table for each pallet
        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1}")
            st.write(f"Pallet Dimension: {pallet_length} × {pallet_width} × {max_pallet_height} cm")
            st.dataframe(pd.DataFrame(pallet["boxes"]))
