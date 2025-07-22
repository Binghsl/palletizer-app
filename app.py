import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="📦 Pallet Layer Simulation with Freeform Leftover Mixing", layout="wide")
st.title(":package: Pallet Layer Simulation - Freeform Leftover Mixing")

st.markdown("""
**Layer stacking rules:**  
1. Group those with the same layer dimension and palletize them (no mixing PNs or dimensions for these full pallets).  
2. Only allow mixed loading (even for different PNs and dimensions) for remaining pallet layers ("leftover layers").  
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

def pack_layers_by_pn_and_dimension(layers):
    # Step 1: Full pallets by PN and layer dimension (no mixing if same dimension)
    pallets = []
    unassigned_layers = []
    df_layers = pd.DataFrame(layers)
    if len(df_layers) == 0:
        return [], []

    # Full pallets by PN and layer dimension
    group_cols = ["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer", "Part No"]
    for key, group in df_layers.groupby(group_cols):
        group = group.copy()
        max_layer = key[4]
        num_full_pallets = len(group) // max_layer
        for i in range(num_full_pallets):
            these_layers = group.iloc[i*max_layer:(i+1)*max_layer]
            pallet_height = these_layers["Layer Height"].sum()
            util = pallet_height / (max_layer * key[2]) * 100 if max_layer > 0 else 0
            pallets.append({
                "Pallet Group": "Full (No Mix)",
                "Part Nos": [these_layers["Part No"].iloc[0]],
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

    return pallets, unassigned_layers

def pack_leftover_layers_any_mix(unassigned_layers):
    # Step 2: Mix loading for remaining layers - allow any combination, fill up to the largest max_layer among leftovers
    pallets = []
    if len(unassigned_layers) == 0:
        return pallets
    df_layers = pd.DataFrame(unassigned_layers)
    # For simplicity, use the largest max_layer among leftovers for mixing
    leftover_layers = df_layers.copy()
    while not leftover_layers.empty:
        # Find the max_layer for the next batch (could also pick min or median if desired)
        max_layer = leftover_layers["Max Layer"].max()
        batch = leftover_layers.iloc[:max_layer]
        pallet_height = batch["Layer Height"].sum()
        # For reporting, use a comma-joined description of dimensions/PNS
        all_pns = sorted(batch["Part No"].unique())
        dim_str = "; ".join(f'{r["Part No"]}:{r["Box Length"]}x{r["Box Width"]}x{r["Box Height"]}' for _, r in batch.iterrows())
        pallets.append({
            "Pallet Group": "Consolidated (Free Mix)",
            "Part Nos": all_pns,
            "Box Length": "Mixed",
            "Box Width": "Mixed",
            "Box Height": "Mixed",
            "Box/Layer": "Mixed",
            "Max Layer": max_layer,
            "Pallet Layers": len(batch),
            "Total Boxes": batch["Boxes in Layer"].sum(),
            "Pallet Height (cm)": pallet_height,
            "Height Utilization (%)": "",  # not meaningful when mixed
            "Layer Details": batch.to_dict("records"),
            "Layer Summary": dim_str
        })
        leftover_layers = leftover_layers.iloc[len(batch):]
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
            "Layer Summary": p.get("Layer Summary", "")
        })
    return pd.DataFrame(rows)

if st.button("Simulate and Consolidate"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        # 1. Break out all layers
        layers = explode_layers(box_df)
        # 2. Full pallets by PN and dimension (no mixing)
        full_pallets, unassigned_layers = pack_layers_by_pn_and_dimension(layers)
        # 3. Remaining layers: allow ANY mix (even across dimension)
        mixed_pallets = pack_leftover_layers_any_mix(unassigned_layers)
        all_pallets = full_pallets + mixed_pallets
        # 4. Create CSV
        csv_df = create_consolidated_csv(all_pallets, pallet_length, pallet_width)
        st.success(f"Total simulated pallets: {len(csv_df)} (including consolidated)")

        st.download_button(
            label="⬇️ Download Pallet Plan CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="pallet_simulation_consolidated.csv",
            mime="text/csv"
        )

        st.dataframe(csv_df)

        # Show each pallet's dimensions at the end
        st.header("Pallet Dimensions Summary")
        for i, p in enumerate(all_pallets):
            if p["Box Length"] == "Mixed":
                st.write(f'Pallet #{i+1}: [Mixed dimensions]')
                st.write(f'  Layers: {p["Pallet Layers"]}, Max Layer: {p["Max Layer"]}, Height: {p["Pallet Height (cm)"]} cm')
                st.write(f'  Layer Summary: {p.get("Layer Summary", "")}')
            else:
                st.write(f'Pallet #{i+1}: {pallet_length} x {pallet_width} x {p["Pallet Height (cm)"]} cm (LxWxH)')
                st.write(f'  Box: {p["Box Length"]}x{p["Box Width"]}x{p["Box Height"]} cm, Layers: {p["Pallet Layers"]}, Max Layer: {p["Max Layer"]}, Height Utilization: {p["Height Utilization (%)"]}%')
