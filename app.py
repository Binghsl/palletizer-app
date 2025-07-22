import streamlit as st
import pandas as pd
import numpy as np
import math
import io

st.set_page_config(page_title="📦 Pallet Layer Simulation with Cross-PN Consolidation", layout="wide")
st.title(":package: Pallet Layer Simulation and Cross-PN Consolidation")

st.markdown("""
**Simulation rules:**  
1. Provide raw data: Part No (PN), box dimensions, box per layer, max layers, quantity  
2. Group PNs with same box dimension  
3. Calculate how many pallet layers are needed  
4. Each pallet layer = (pallet length × pallet width × box height)  
5. If box count < box per layer, treat as full layer  
6. Pallets with <50% height utilization can be consolidated even across different PNs  
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

def explode_layers(df):
    # For all rows, break out the required number of layers, using "full layer" if not enough quantity
    layers = []
    for idx, row in df.iterrows():
        qty_left = row["Quantity"]
        for layer_idx in range(math.ceil(row["Quantity"] / row["Box/Layer"])):
            layer_boxes = min(row["Box/Layer"], qty_left)
            if layer_boxes < row["Box/Layer"] and qty_left > 0:
                layer_boxes = row["Box/Layer"]
            layers.append({
                "Part No": row["Part No"],
                "Box Length": row["Length (cm)"],
                "Box Width": row["Width (cm)"],
                "Box Height": row["Height (cm)"],
                "Box/Layer": row["Box/Layer"],
                "Max Layer": row["Max Layer"],
                "Boxes in Layer": layer_boxes,
                "Layer Height": row["Height (cm)"],
                "Layer Source": idx
            })
            qty_left -= min(layer_boxes, qty_left)
    return layers

def pack_layers_into_pallets(layers):
    # Each pallet can have up to max_layer, same box dims/layer; fill >50% first, then consolidate
    # Group layers by (Box Length, Box Width, Box Height, Box/Layer, Max Layer, Part No)
    from collections import defaultdict

    # First: assign full pallets
    pallets = []
    unassigned_layers = []
    for key, group in pd.DataFrame(layers).groupby(["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer", "Part No"]):
        group = group.copy()
        max_layer = key[4]
        num_full_pallets = len(group) // max_layer
        for i in range(num_full_pallets):
            these_layers = group.iloc[i*max_layer:(i+1)*max_layer]
            pallet_height = these_layers["Layer Height"].sum()
            util = pallet_height / (max_layer * key[2]) * 100 if max_layer > 0 else 0
            pallets.append({
                "Pallet Group": "Original",
                "Part Nos": these_layers["Part No"].unique(),
                "Box Length": key[0],
                "Box Width": key[1],
                "Box Height": key[2],
                "Box/Layer": key[3],
                "Max Layer": max_layer,
                "Pallet Layers": max_layer,
                "Total Boxes": these_layers["Boxes in Layer"].sum(),
                "Pallet Height (cm)": pallet_height,
                "Height Utilization (%)": round(util, 1),
                "Layer Details": these_layers.to_dict("records")
            })
        # Remainder goes to unassigned
        remain = len(group) % max_layer
        if remain > 0:
            remain_layers = group.iloc[-remain:]
            for _, lrow in remain_layers.iterrows():
                unassigned_layers.append(lrow)

    # Second: try to pack all unassigned layers together, regardless of PN, as long as box/layer, dims, max_layer match
    # Group by box dimension, box/layer, max_layer
    if len(unassigned_layers) > 0:
        df_unassigned = pd.DataFrame(unassigned_layers)
        grouped = df_unassigned.groupby(["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer"])
        for key, group in grouped:
            layers_group = group.copy()
            max_layer = key[4]
            used = set()
            # Keep packing until all layers are assigned
            idxs = list(layers_group.index)
            while idxs:
                these_idxs = idxs[:max_layer]
                these_layers = layers_group.loc[these_idxs]
                pallet_height = these_layers["Layer Height"].sum()
                util = pallet_height / (max_layer * key[2]) * 100 if max_layer > 0 else 0
                pallets.append({
                    "Pallet Group": "Consolidated",
                    "Part Nos": sorted(these_layers["Part No"].unique()),
                    "Box Length": key[0],
                    "Box Width": key[1],
                    "Box Height": key[2],
                    "Box/Layer": key[3],
                    "Max Layer": max_layer,
                    "Pallet Layers": len(these_layers),
                    "Total Boxes": these_layers["Boxes in Layer"].sum(),
                    "Pallet Height (cm)": pallet_height,
                    "Height Utilization (%)": round(util, 1),
                    "Layer Details": these_layers.to_dict("records")
                })
                idxs = idxs[len(these_idxs):]
    return pallets

def create_consolidated_csv(pallets, pallet_L, pallet_W):
    rows = []
    for i, p in enumerate(pallets):
        rows.append({
            "Pallet No": i+1,
            "Pallet Group": p["Pallet Group"],
            "Part Nos": ", ".join(map(str, p["Part Nos"])),
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
        # 1. Break out all layers
        layers = explode_layers(box_df)
        # 2. Pack layers into pallets with cross-PN consolidation
        pallets = pack_layers_into_pallets(layers)
        # 3. Create CSV
        csv_df = create_consolidated_csv(pallets, pallet_length, pallet_width)
        st.success(f"Total simulated pallets: {len(csv_df)} (including consolidated)")

        st.download_button(
            label="⬇️ Download Pallet Plan CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="pallet_simulation_consolidated.csv",
            mime="text/csv"
        )

        st.dataframe(csv_df)
