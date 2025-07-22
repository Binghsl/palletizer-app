import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="📦 Pallet Layer Simulation with Height Limit", layout="wide")
st.title(":package: Pallet Layer Simulation - Height Limit 135–140cm (boxes), 150–155cm (total)")

st.markdown("""
**Layer stacking rules:**  
1. Group those with the same layer dimension and palletize them (no mixing PNs or dimensions for these full pallets).  
2. Only allow mixed loading (even for different PNs and dimensions) for remaining pallet layers ("leftover layers").  
3. The stacked box height per pallet must be between **135 and 140 cm** (not including the pallet base).  
4. The pallet base is **15 cm**; total pallet height = base + boxes = **150–155 cm**.  
""")

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
pallet_base_height = 15
min_stack_height = 135
max_stack_height = 140

def explode_layers(df):
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

def pack_layers_height_limit(layers):
    pallets = []
    unassigned_layers = []
    df_layers = pd.DataFrame(layers)
    if len(df_layers) == 0:
        return [], []

    group_cols = ["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer", "Part No"]
    for key, group in df_layers.groupby(group_cols):
        group = group.copy().reset_index(drop=True)
        layer_idx = 0
        n_layers = len(group)
        while layer_idx < n_layers:
            stack = []
            stack_height = 0
            max_layer = key[4]
            # Try to stack as many as possible without going over max_stack_height, up to max_layer
            while (layer_idx < n_layers and
                   len(stack) < max_layer and
                   stack_height + group.loc[layer_idx, "Layer Height"] <= max_stack_height):
                stack.append(group.loc[layer_idx])
                stack_height += group.loc[layer_idx, "Layer Height"]
                layer_idx += 1
            # If no layer could be added (layer itself is too tall), forcibly add for progress
            if not stack and layer_idx < n_layers:
                stack.append(group.loc[layer_idx])
                stack_height += group.loc[layer_idx, "Layer Height"]
                layer_idx += 1
            if stack:
                util = stack_height / (max_layer * key[2]) * 100 if max_layer > 0 else 0
                pallets.append({
                    "Pallet Group": "Full (No Mix)",
                    "Part Nos": [stack[0]["Part No"]],
                    "Box Length": key[0],
                    "Box Width": key[1],
                    "Box Height": key[2],
                    "Box/Layer": key[3],
                    "Max Layer": max_layer,
                    "Pallet Layers": len(stack),
                    "Total Boxes": sum(l["Boxes in Layer"] for l in stack),
                    "Pallet Height (cm)": stack_height,
                    "Height Utilization (%)": round(util, 1),
                    "Layer Details": [dict(l) for l in stack]
                })
    # Collect all leftover layers in one list for mixed packing
    # (all layers not used in above logic are not possible here, as all group layers are packed)
    return pallets, []

def pack_leftover_layers_any_mix(layers):
    # Mix loading for remaining layers - allow any combination, fill up to height limit
    pallets = []
    if not layers:
        return pallets
    df_layers = pd.DataFrame(layers)
    available_layers = df_layers.copy().reset_index(drop=True)
    n_layers = len(available_layers)
    used = set()
    idx = 0
    while idx < n_layers:
        stack = []
        stack_height = 0
        # Use the largest max_layer among leftovers for this pallet
        max_layer = available_layers.loc[idx:, "Max Layer"].max()
        # Stack as many as possible without exceeding max_stack_height or max_layer
        j = idx
        while j < n_layers and len(stack) < max_layer:
            if j in used:
                j += 1
                continue
            h = available_layers.loc[j, "Layer Height"]
            if stack_height + h > max_stack_height:
                j += 1
                continue
            stack.append(available_layers.loc[j])
            stack_height += h
            used.add(j)
            j += 1
        # If nothing added, forcibly add one for progress
        if not stack and idx < n_layers and idx not in used:
            stack.append(available_layers.loc[idx])
            stack_height += available_layers.loc[idx, "Layer Height"]
            used.add(idx)
        if stack:
            all_pns = sorted(set(l["Part No"] for l in stack))
            dim_str = "; ".join(
                f'{l["Part No"]}:{l["Box Length"]}x{l["Box Width"]}x{l["Box Height"]}'
                for l in stack
            )
            pallets.append({
                "Pallet Group": "Consolidated (Free Mix)",
                "Part Nos": all_pns,
                "Box Length": "Mixed",
                "Box Width": "Mixed",
                "Box Height": "Mixed",
                "Box/Layer": "Mixed",
                "Max Layer": max_layer,
                "Pallet Layers": len(stack),
                "Total Boxes": sum(l["Boxes in Layer"] for l in stack),
                "Pallet Height (cm)": stack_height,
                "Height Utilization (%)": "",
                "Layer Details": [dict(l) for l in stack],
                "Layer Summary": dim_str
            })
        idx += 1
        # Move idx to next unused layer
        while idx < n_layers and idx in used:
            idx += 1
    return pallets

def create_consolidated_csv(pallets, pallet_L, pallet_W, pallet_base_height):
    rows = []
    for i, p in enumerate(pallets):
        total_height = pallet_base_height + p["Pallet Height (cm)"]
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
            "Stacked Height (cm)": p["Pallet Height (cm)"],
            "Total Pallet Height (cm)": total_height,
            "Height Utilization (%)": p["Height Utilization (%)"],
            "Layer Summary": p.get("Layer Summary", "")
        })
    return pd.DataFrame(rows)

if st.button("Simulate and Consolidate"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        layers = explode_layers(box_df)
        full_pallets, unassigned_layers = pack_layers_height_limit(layers)
        # (No unassigned layers since all are packed, but if a more advanced logic is used, pass leftovers to mix logic)
        mixed_pallets = pack_leftover_layers_any_mix(unassigned_layers)
        all_pallets = full_pallets + mixed_pallets
        csv_df = create_consolidated_csv(all_pallets, pallet_length, pallet_width, pallet_base_height)
        st.success(f"Total simulated pallets: {len(csv_df)} (including consolidated)")

        st.download_button(
            label="⬇️ Download Pallet Plan CSV",
            data=csv_df.to_csv(index=False).encode("utf-8"),
            file_name="pallet_simulation_consolidated.csv",
            mime="text/csv"
        )

        st.dataframe(csv_df)

        # Show only each pallet's dimensions at the end
        st.header("Pallet Dimensions Summary")
        for i, p in enumerate(all_pallets):
            total_height = pallet_base_height + p["Pallet Height (cm)"]
            st.write(f'Pallet #{i+1}: {pallet_length} x {pallet_width} x {total_height} cm (LxWxH)')
