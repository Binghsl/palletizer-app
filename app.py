import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="📦 CBM Palletizer", layout="wide")
st.title(":package: Palletizer based on CBM (Cubic Meter) Optimization")

st.markdown("""
Enter box types with quantity and dimensions.  
The app calculates how to optimally pack boxes on pallets based on CBM (cubic meter) utilization.  
No geometric packing—boxes are packed greedily by volume until the pallet volume is reached.
You can download a single CSV file containing all pallets' packing lists.
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

def calculate_cbm(length_cm, width_cm, height_cm):
    # Convert cm to m
    return (length_cm / 100) * (width_cm / 100) * (height_cm / 100)

def cbm_palletize(boxes, pallet_L, pallet_W, pallet_H, pallet_base_H):
    # Pallet usable height (without base)
    usable_H = pallet_H
    pallet_cbm = calculate_cbm(pallet_L, pallet_W, usable_H)
    all_boxes = boxes.copy()
    all_boxes["Box CBM"] = calculate_cbm(all_boxes["Length (cm)"], all_boxes["Width (cm)"], all_boxes["Height (cm)"])
    all_boxes["Total CBM"] = all_boxes["Box CBM"] * all_boxes["Quantity"]
    pallets = []
    remaining = all_boxes.copy()
    while remaining["Quantity"].sum() > 0:
        pallet = []
        pallet_used_cbm = 0.0
        # Sort boxes by CBM descending (try bigger boxes first)
        sorted_boxes = remaining.sort_values(by="Box CBM", ascending=False)
        for idx, box in sorted_boxes.iterrows():
            box_cbm = box["Box CBM"]
            qty_available = int(box["Quantity"])
            qty_to_pack = min(qty_available, int((pallet_cbm - pallet_used_cbm) // box_cbm))
            if qty_to_pack > 0:
                pallet.append({
                    "Part No": box["Part No"],
                    "Packed Qty": qty_to_pack,
                    "Box CBM": box_cbm,
                    "Total Packed CBM": qty_to_pack * box_cbm,
                    "Dims (cm)": f'{box["Length (cm)"]}x{box["Width (cm)"]}x{box["Height (cm)"]}'
                })
                pallet_used_cbm += qty_to_pack * box_cbm
                remaining.at[idx, "Quantity"] -= qty_to_pack
        pallets.append({
            "boxes": pallet,
            "pallet_cbm_used": pallet_used_cbm,
            "pallet_cbm_total": pallet_cbm,
            "utilization": pallet_used_cbm / pallet_cbm * 100
        })
    return pallets, remaining

def create_single_csv_packing_list(pallets):
    # Create a single DataFrame for all pallets
    all_rows = []
    for i, pallet in enumerate(pallets):
        for item in pallet["boxes"]:
            all_rows.append({
                "Pallet No": i + 1,
                "Part No": item["Part No"],
                "Packed Qty": item["Packed Qty"],
                "Dims (cm)": item["Dims (cm)"],
                "Box CBM": item["Box CBM"],
                "Total Packed CBM": item["Total Packed CBM"],
                "Pallet CBM Used (m³)": pallet["pallet_cbm_used"],
                "Pallet CBM Total (m³)": pallet["pallet_cbm_total"],
                "Utilization (%)": pallet["utilization"]
            })
    return pd.DataFrame(all_rows)

if st.button(":mag: Calculate CBM Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets, remaining = cbm_palletize(boxes, pallet_length, pallet_width, max_pallet_height, pallet_base_height)
        st.success(f"Total pallets needed: {len(pallets)}")

        st.subheader(":straight_ruler: Pallet CBM")
        st.write(f"Pallet dimensions: {pallet_length} × {pallet_width} × {max_pallet_height} cm")
        st.write(f"Pallet CBM: {calculate_cbm(pallet_length, pallet_width, max_pallet_height):.3f} m³")

        # All pallets in one CSV
        single_df = create_single_csv_packing_list(pallets)
        st.download_button(
            label="⬇️ Download FULL packing list (all pallets in one CSV)",
            data=single_df.to_csv(index=False).encode("utf-8"),
            file_name="all_pallets_packing_list.csv",
            mime="text/csv"
        )

        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1}")
            st.write(f"CBM Used: {pallet['pallet_cbm_used']:.3f} m³ / {pallet['pallet_cbm_total']:.3f} m³")
            st.write(f"Utilization: {pallet['utilization']:.1f}%")
            st.dataframe(pd.DataFrame(pallet["boxes"]))
        if remaining["Quantity"].sum() > 0:
            st.warning(f"Boxes not packed: {remaining['Quantity'].sum()}")
            st.dataframe(remaining)
