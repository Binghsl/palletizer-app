import streamlit as st
import pandas as pd
from itertools import permutations

st.set_page_config(page_title="📦 Multi-Box Palletizer", layout="wide")
st.title("📦 Multi-Box Palletizer (Standard Pallet)")

st.markdown("""
Enter up to 10 box types with quantity, dimensions, and rotation option.
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
""")

# Sidebar pallet settings
st.sidebar.header("🧱 Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)

# Box input count
box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=3)

# Default box input data
default_data = [{
    "Box Name": f"Box {i+1}",
    "Length (cm)": 30,
    "Width (cm)": 20,
    "Height (cm)": 15,
    "Quantity": 100,
    "Allow Rotation": True
} for i in range(box_count)]

box_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    use_container_width=True,
    key="box_input"
)

def calculate_fit_for_box(pallet_L, pallet_W, max_H, box_L, box_W, box_H, qty, allow_rotate):
    best_fit = 0
    best_layout = None

    orientations = permutations((box_L, box_W, box_H)) if allow_rotate else [(box_L, box_W, box_H)]

    for orient in orientations:
        l, w, h = orient
        fit_L = int(pallet_L // l)
        fit_W = int(pallet_W // w)
        fit_H = int(max_H // h)
        total_fit = fit_L * fit_W * fit_H
        placed = min(qty, total_fit)
        if total_fit > best_fit:
            best_fit = total_fit
            best_layout = {
                "orientation": (l, w, h),
                "fit_L": fit_L,
                "fit_W": fit_W,
                "fit_H": fit_H,
                "placed": placed,
                "height": fit_H * h
            }
    return best_layout, best_fit

def pack_boxes_on_pallets(boxes, pallet_L, pallet_W, max_H):
    pallets = []
    remaining_boxes = boxes.copy()

    while remaining_boxes["Quantity"].sum() > 0:
        pallet = {"boxes": [], "height": 0}
        pallet_space_height = max_H
        placed_any = False

        for idx, row in remaining_boxes.iterrows():
            if row["Quantity"] == 0:
                continue

            layout, max_fit = calculate_fit_for_box(
                pallet_L, pallet_W, pallet_space_height,
                row["Length (cm)"], row["Width (cm)"], row["Height (cm)"],
                row["Quantity"], row["Allow Rotation"]
            )
            if layout is None or layout["placed"] == 0:
                continue

            placed = layout["placed"]
            pallet["boxes"].append({
                "Box Name": row["Box Name"],
                "Placed": placed,
                "Orientation": layout["orientation"],
                "Boxes per Layer": layout["fit_L"] * layout["fit_W"],
                "Layers": layout["fit_H"],
                "Box Dimensions (L×W×H)": (row["Length (cm)"], row["Width (cm)"], row["Height (cm)"]),
                "Pallet Layer Height": layout["height"]
            })

            if layout["height"] > pallet["height"]:
                pallet["height"] = layout["height"]

            remaining_boxes.at[idx, "Quantity"] -= placed
            placed_any = True

        if not placed_any:
            st.warning("No more boxes can be placed; stopping to prevent infinite loop.")
            break

        pallets.append(pallet)

        if len(pallets) > 100:
            st.warning("Too many pallets required; stopping calculation.")
            break

    return pallets, remaining_boxes

if st.button("🔍 Calculate Palletization"):
    if box_df.empty:
        st.error("Please enter box data")
    else:
        boxes = box_df.copy()
        pallets, remaining = pack_boxes_on_pallets(boxes, pallet_length, pallet_width, max_pallet_height)

        st.success(f"✅ Palletization complete! Total pallets needed: {len(pallets)}")

        for i, pallet in enumerate(pallets):
            st.markdown(f"### 📦 Pallet #{i+1} (Height: {pallet['height']:.1f} cm)")
            df = pd.DataFrame(pallet["boxes"])
            st.dataframe(df)

        if remaining["Quantity"].sum() > 0:
            st.warning(f"⚠️ Remaining boxes not placed: {remaining['Quantity'].sum()}")
            st.dataframe(remaining)

        def pallets_summary_df(pallets):
            data = []
            for i, p in enumerate(pallets):
                for b in p["boxes"]:
                    data.append({
                        "Pallet #": i + 1,
                        "Box Name": b["Box Name"],
                        "Placed": b["Placed"],
                        "Orientation": str(b["Orientation"]),
                        "Boxes per Layer": b["Boxes per Layer"],
                        "Layers": b["Layers"],
                        "Pallet Height (cm)": p["height"]
                    })
            return pd.DataFrame(data)

        summary_df = pallets_summary_df(pallets)
        csv = summary_df.to_csv(index=False)
        st.download_button("⬇️ Download Palletization Summary CSV", csv, "palletization_summary.csv", "text/csv")
