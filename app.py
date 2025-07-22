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
    {"Part No": "51700", "Length (cm)": 60, "Width (cm)": 29, "Height (cm)": 29, "Quantity": 14, "Box/Layer": 6, "Max Layer": 4},
    {"Part No": "52363", "Length (cm)": 54, "Width (cm)": 38, "Height (cm)": 31, "Quantity": 5, "Box/Layer": 5, "Max Layer": 4},
    {"Part No": "61385", "Length (cm)": 51, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 78, "Box/Layer": 6, "Max Layer": 4},
    {"Part No": "61386", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 52, "Box/Layer": 8, "Max Layer": 4},
    {"Part No": "61387", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 18, "Box/Layer": 8, "Max Layer": 4},
    {"Part No": "61388", "Length (cm)": 41, "Width (cm)": 35, "Height (cm)": 30, "Quantity": 52, "Box/Layer": 8, "Max Layer": 4},
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
    # How many full layers needed for this group (note: do not exceed max_layer for a single pallet)
    needed_layers = math.ceil(total_qty / box_per_layer)
    layer_plan = []
    qty_left = total_qty
    for i in range(needed_layers):
        # Each layer is simulated as full even if qty less (rule 5)
        boxes_this_layer = min(box_per_layer, qty_left)
        if boxes_this_layer < box_per_layer and qty_left > 0:
            boxes_this_layer = box_per_layer
        layer_plan.append({
            "boxes": boxes_this_layer,
            "box_height": h
        })
        qty_left -= min(boxes_this_layer, qty_left)
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
        num_layers_total = len(layers)
        # Split into pallets of max_layer per pallet
        pointer = 0
        while pointer < num_layers_total:
            this_pallet_layers = layers[pointer:pointer+g["max_layer"]]
            total_boxes = sum([x["boxes"] for x in this_pallet_layers])
            pallet_height = sum([x["box_height"] for x in this_pallet_layers])
            max_pallet_height = g["max_layer"] * g["dims"][2]
            height_util = (pallet_height / max_pallet_height) if max_pallet_height > 0 else 0
            pallets.append({
                "Part Nos": ",".join(g["pns"]),
                "Box Length": g["dims"][0],
                "Box Width": g["dims"][1],
                "Box Height": g["dims"][2],
                "Box/Layer": g["box_per_layer"],
                "Max Layer": g["max_layer"],
                "Pallet Layers": len(this_pallet_layers),
                "Total Boxes": total_boxes,
                "Pallet Height (cm)": pallet_height,
                "Height Utilization (%)": round(height_util * 100, 1),
                "Layer Details": this_pallet_layers,
                "Pallet Group": None,  # For consolidation step
            })
            pointer += g["max_layer"]
    return pallets

def consolidate_low_util_pallets(pallets, min_util=50.0):
    # Find all pallets with <50% utilization
    low_util = [p for p in pallets if p["Height Utilization (%)"] < min_util]
    good_util = [p for p in pallets if p["Height Utilization (%)"] >= min_util]
    # Try to combine low-util pallets of same box dimension
    consolidated = []
    used = set()
    for i, base in enumerate(low_util):
        if i in used:
            continue
        merged_layers = base["Layer Details"].copy()
        merged_boxes = base["Total Boxes"]
        merged_height = base["Pallet Height (cm)"]
        merged_pns = set(base["Part Nos"].split(","))
        max_layers = base["Max Layer"]
        box_height = base["Box Height"]
        # Try to merge with others
        for j, other in enumerate(low_util):
            if j <= i or j in used:
                continue
            # Only merge if box dims match and max_layer not exceeded
            if (other["Box Length"], other["Box Width"], other["Box Height"], other["Box/Layer"], other["Max Layer"]) == \
               (base["Box Length"], base["Box Width"], base["Box Height"], base["Box/Layer"], base["Max Layer"]):
                if len(merged_layers) + len(other["Layer Details"]) <= max_layers:
                    merged_layers.extend(other["Layer Details"])
                    merged_boxes += other["Total Boxes"]
                    merged_height += other["Pallet Height (cm)"]
                    merged_pns.update(other["Part Nos"].split(","))
                    used.add(j)
        util = merged_height / (max_layers * box_height) * 100 if max_layers > 0 else 0
        consolidated.append({
            "Part Nos": ",".join(sorted(merged_pns)),
            "Box Length": base["Box Length"],
            "Box Width": base["Box Width"],
            "Box Height": base["Box Height"],
            "Box/Layer": base["Box/Layer"],
            "Max Layer": base["Max Layer"],
            "Pallet Layers": len(merged_layers),
            "Total Boxes": merged_boxes,
            "Pallet Height (cm)": merged_height,
            "Height Utilization (%)": round(util, 1),
            "Layer Details": merged_layers,
            "Pallet Group": "Consolidated"
        })
        used.add(i)
    # Mark good-util pallets as "Original"
    for p in good_util:
        p["Pallet Group"] = "Original"
    return good_util + consolidated

def create_consolidated_csv(pallets, pallet_L, pallet_W):
    rows = []
    for i, p in enumerate(pallets):
        rows.append({
            "Pallet No": i+1,
            "Pallet Group": p["Pallet Group"],
            "Part Nos": p["Part Nos"],
            "Box Length (cm)": p["Box Length"],
            "Box Width (cm)": p["Box Width"],
            "Box Height (cm)": p["Box Height"],
            "Pallet Length (cm)": pallet_L,
            "Pallet Width (cm)": pallet_W,
            "Box/Layer": p["Box/Layer"],
            "Max Layer": p["Max Layer"],
            "Pallet Layers": p["Pallet Layers"],
            "Total Boxes": p["Total Boxes"],
            "Pallet Height (cm)": p["Pallet Height (cm)"],
            "Height Utilization (%)": p["Height Utilization (%)"],
        })
    return pd.DataFrame(rows)

if st.button("Simulate and Consolidate"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        # Step 1: Group PN with same box dimension
        grouped = group_boxes_by_dimension(box_df)
        # Step 2: Simulate layers for each group
        group_layers = [simulate_layers_for_group(g) for g in grouped]
        # Step 3: Build pallets from layers
        pallets = build_pallets_from_layers(group_layers)
        # Step 4: Consolidate low-utilization pallets
        consolidated = consolidate_low_util_pallets(pallets, min_util=50.0)
        # Step 5: Create consolidated CSV
        csv_df = create_consolidated_csv(consolidated, pallet_length, pallet_width)
        st.success(f"Total simulated pallets: {len(csv_df)} (including consolidated)")

        st.download_button(
            label="⬇️ Download Pallet Plan CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="pallet_simulation_consolidated.csv",
            mime="text/csv"
        )

        st.dataframe(csv_df)
