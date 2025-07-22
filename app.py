import streamlit as st
import pandas as pd
import numpy as np
import math
import io

st.set_page_config(page_title="📦 Pallet Layer Simulation with Consolidation", layout="wide")
st.title(":package: Pallet Layer Simulation and Consolidation")

st.markdown("""
**Simulation rules:**  
1. Provide raw data: Part No (PN), box dimensions, box per layer, max layers, quantity  
2. Group PNs with same box dimension  
3. Calculate how many pallet layers are needed  
4. Each pallet layer = (pallet length × pallet width × box height)  
5. If box count < box per layer, treat as full layer  
6. Pallets with <50% height utilization are consolidated  
""")

# --- User Input ---
st.header("Upload or Edit Raw Data")
default_data = [
    {"Part No": "51700", "Length (cm)": 30, "Width (cm)": 29, "Height (cm)": 60, "Box/Layer": 4, "Max Layer": 3, "Quantity": 14},
    {"Part No": "52363", "Length (cm)": 54, "Width (cm)": 38, "Height (cm)": 31, "Box/Layer": 2, "Max Layer": 4, "Quantity": 5},
    {"Part No": "61385", "Length (cm)": 51, "Width (cm)": 35, "Height (cm)": 30, "Box/Layer": 6, "Max Layer": 5, "Quantity": 78},
    {"Part No": "61386", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Box/Layer": 6, "Max Layer": 5, "Quantity": 52},
    {"Part No": "61387", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Box/Layer": 6, "Max Layer": 5, "Quantity": 18},
    {"Part No": "61388", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Box/Layer": 6, "Max Layer": 5, "Quantity": 52},
]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

pallet_length = st.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)

def group_boxes_by_dimension(df):
    grouped = df.groupby(["Length (cm)", "Width (cm)", "Height (cm)", "Box/Layer", "Max Layer"])
    result = []
    for dims, group in grouped:
        result.append({
            "dims": dims,
            "pns": list(group["Part No"]),
            "total_qty": group["Quantity"].sum(),
            "rows": group.to_dict("records")
        })
    return result

def simulate_layers_for_group(group):
    l, w, h, box_per_layer, max_layer = group["dims"]
    total_qty = group["total_qty"]
    # How many full layers needed for this group
    needed_layers = math.ceil(total_qty / box_per_layer)
    needed_layers = min(needed_layers, max_layer)  # do not exceed max_layer
    # For simulation, if box count < box per layer, treat as full layer (rule 5)
    layer_plan = []
    qty_left = total_qty
    for i in range(needed_layers):
        this_layer_boxes = min(box_per_layer, qty_left) if qty_left > 0 else 0
        if this_layer_boxes < box_per_layer and qty_left > 0:
            this_layer_boxes = box_per_layer  # simulate as full layer
        layer_plan.append({
            "boxes": this_layer_boxes,
            "box_height": h
        })
        qty_left -= min(this_layer_boxes, qty_left)
    return {
        "dims": (l, w, h),
        "box_per_layer": box_per_layer,
        "max_layer": max_layer,
        "layers": layer_plan,
        "pns": group["pns"]
    }

def build_pallets_from_layers(groups):
    pallets = []
    for g in groups:
        layers = g["layers"]
        layers_used = len(layers)
        for i in range(0, layers_used, g["max_layer"]):
            # Pallet consists of up to max_layer layers
            these_layers = layers[i:i+g["max_layer"]]
            total_boxes = sum([x["boxes"] for x in these_layers])
            pallet_height = sum([x["box_height"] for x in these_layers])
            max_possible_height = g["box_per_layer"] *
