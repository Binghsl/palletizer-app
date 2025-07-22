import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="📦 Pallet Layer Simulation (PN Priority, No Dim Mixing)", layout="wide")
st.title(":package: Pallet Layer Simulation - Prioritize Same PN, No Box Dim Mixing")

st.markdown("""
**Layer stacking rules:**  
1. **Full pallets:**  
   - First, stack by Part No **and** box dimensions (Box Length, Box Width, Box Height, Box/Layer, Max Layer).  
   - Stack layers on a pallet up to the max allowed by Max Layer and box height sum 135–140 cm.  
   - If leftover layers of the same box dimension exist from different PNs, fill additional full pallets by dimension only (PNs can be mixed, but never mix box dimensions).  
2. **Leftover layers:**  
   - Any leftovers are freely mixed (any PN, any dimension) up to the largest available Max Layer and total stacked box height 135–140 cm.
3. **Pallet base is 15 cm**, so total pallet height is 150–155 cm.
4. For "mixed" pallets, box columns show "Mixed" and a Layer Summary describes the contents.
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
        for _ in range(math.ceil(row["Quantity"] / row["Box/Layer"])):
            layer_boxes = min(row["Box/Layer"], qty_left)
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
            qty_left -= layer_boxes
    return layers

def stack_layers_by_group(df_layers, group_cols, max_stack_height):
    pallets = []
    unassigned_layers = []
    for key, group in df_layers.groupby(group_cols):
        group = group.copy().reset_index(drop=True)
        n_layers = len(group)
        used = np.zeros(n_layers, dtype=bool)
        idx = 0
        while idx < n_layers:
            stack = []
            stack_height = 0
            max_layer = group.loc[0, "Max Layer"]
            j = idx
            while j < n_layers and len(stack) < max_layer:
                h = group.loc[j, "Layer Height"]
                if used[j]:
                    j += 1
                    continue
                if stack_height + h > max_stack_height:
                    break
                stack.append(group.loc[j])
                stack_height += h
                used[j] = True
                j += 1
            if not stack and idx < n_layers and not used[idx]:
                stack.append(group.loc[idx])
                stack_height += group.loc[idx, "Layer Height"]
                used[idx] = True
            if stack:
                # For single-PN, report single; for mixed, report all PNs
                part_nos = sorted(set(l["Part No"] for l in stack))
                util = stack_height / (max_layer * group.loc[0, "Box Height"]) * 100 if max_layer > 0 else 0
                pallets.append({
                    "Pallet Group": "Full (No Mix of Dimensions)" if len(part_nos) == 1 else "Full (Mixed PN, No Dim Mix)",
                    "Part Nos": part_nos,
                    "Box Length": group.loc[0, "Box Length"],
                    "Box Width": group.loc[0, "Box Width"],
                    "Box Height": group.loc[0, "Box Height"],
                    "Box/Layer": group.loc[0, "Box/Layer"],
                    "Max Layer": max_layer,
                    "Pallet Layers": len(stack),
                    "Total Boxes": sum(l["Boxes in Layer"] for l in stack),
                    "Pallet Height (cm)": stack_height,
                    "Height Utilization (%)": round(util, 1),
                    "Layer Details": [dict(l) for l in stack]
                })
            idx += 1
            while idx < n_layers and used[idx]:
                idx += 1
        # Any unused layers (shouldn't happen, but for safety)
        for i in range(n_layers):
            if not used[i]:
                unassigned_layers.append(group.loc[i])
    return pallets, unassigned_layers

def priority_full_pallets(layers):
    df_layers = pd.DataFrame(layers)
    # 1. Priority: stack by (Box Length, Box Width, Box Height, Box/Layer, Max Layer, Part No) -> single-PN full pallets
    pallets_1, leftovers_1 = stack_layers_by_group(
        df_layers, ["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer", "Part No"], max_stack_height
    )
    # 2. Next: stack by (Box Length, Box Width, Box Height, Box/Layer, Max Layer) for those leftovers (mixed PN, but dimensions match)
    if leftovers_1:
        leftovers_df2 = pd.DataFrame(leftovers_1)
        pallets_2, leftovers_2 = stack_layers_by_group(
            leftovers_df2, ["Box Length", "Box Width", "Box Height", "Box/Layer", "Max Layer"], max_stack_height
        )
    else:
        pallets_2, leftovers_2 = [], []
    return pallets_1 + pallets_2, leftovers_2

def pack_leftover_layers_any_mix(unassigned_layers):
    pallets = []
    if not unassigned_layers:
        return pallets
    df_layers = pd.DataFrame(unassigned_layers)
    available_layers = df_layers.copy().reset_index(drop=True)
    n_layers = len(available_layers)
    used = np.zeros(n_layers, dtype=bool)
    idx = 0
    while idx < n_layers:
        stack = []
        stack_height = 0
        not_used_idxs = [i for i in range(n_layers) if not used[i]]
        if not not_used_idxs:
            break
        max_layer = available_layers.loc[not_used_idxs, "Max Layer"].max()
        for j in not_used_idxs:
            h = available_layers.loc[j, "Layer Height"]
            if len(stack) >= max_layer:
                break
            if stack_height + h > max_stack_height:
                continue
            stack.append(available_layers.loc[j])
            stack_height += h
            used[j] = True
        if not stack:
            j = not_used_idxs[0]
            stack.append(available_layers.loc[j])
            stack_height += available_layers.loc[j, "Layer Height"]
            used[j] = True
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
        while idx < n_layers and used[idx]:
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
        full_pallets, unassigned_layers = priority_full_pallets(layers)
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

        st.header("Pallet Dimensions Summary")
        for i, p in enumerate(all_pallets):
            total_height = pallet_base_height + p["Pallet Height (cm)"]
            st.write(f'Pallet #{i+1}: {pallet_length} x {pallet_width} x {total_height} cm (LxWxH)')
