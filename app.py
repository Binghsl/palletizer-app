import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import box as shapely_box

# Constants
STANDARD_PALLET_SIZE = (120, 100, 15)  # cm (L, W, H)
MAX_PALLET_HEIGHT = 180  # cm including pallet base

# --- Box Packing Logic ---
def pack_boxes_on_pallets(boxes, pallet_size, max_height_cm, allow_rotation=True):
    placed_boxes = []
    remaining_boxes = []

    # Flatten all boxes
    all_boxes = []
    for item in boxes:
        for _ in range(int(item["Quantity"])):
            all_boxes.append({
                "Part No": item["Part No"],
                "L": item["L"],
                "W": item["W"],
                "H": item["H"],
                "color": item["color"]
            })

    pallet_L, pallet_W, pallet_base_H = pallet_size
    max_stack_height = max_height_cm - pallet_base_H

    z_cursor = 0

    def can_place(new_box, placed, pallet_L, pallet_W):
        new_shape = shapely_box(
            new_box["x"],
            new_box["y"],
            new_box["x"] + new_box["L"],
            new_box["y"] + new_box["W"]
        )
        if new_box["x"] + new_box["L"] > pallet_L or new_box["y"] + new_box["W"] > pallet_W:
            return False
        for b in placed:
            b_shape = shapely_box(
                b["x"],
                b["y"],
                b["x"] + b["L"],
                b["y"] + b["W"]
            )
            if new_shape.intersects(b_shape):
                return False
        return True

    while all_boxes and z_cursor + pallet_base_H <= max_stack_height:
        placed_in_layer = []
        x_cursor = 0
        y_cursor = 0
        row_max_height = 0
        remaining_boxes = []

        while all_boxes:
            box = all_boxes.pop(0)

            orientations = [(box["L"], box["W"])]
            if allow_rotation and box["L"] != box["W"]:
                orientations.append((box["W"], box["L"]))

            placed = False
            for L_try, W_try in orientations:
                trial_box = {
                    **box,
                    "L": L_try,
                    "W": W_try,
                    "x": x_cursor,
                    "y": y_cursor,
                    "z": z_cursor
                }

                if can_place(trial_box, placed_in_layer, pallet_L, pallet_W):
                    trial_box["H"] = box["H"]
                    placed_in_layer.append(trial_box)
                    x_cursor += trial_box["L"]
                    row_max_height = max(row_max_height, trial_box["H"])

                    if x_cursor >= pallet_L:
                        x_cursor = 0
                        y_cursor += trial_box["W"]
                        if y_cursor >= pallet_W:
                            break
                    placed = True
                    break

            if not placed:
                remaining_boxes.append(box)

        if not placed_in_layer:
            break

        placed_boxes.extend(placed_in_layer)
        all_boxes = remaining_boxes
        z_cursor += row_max_height

    return placed_boxes

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("📦 Multi-Part Palletizer with 3D Visualization")

with st.sidebar:
    st.header("Upload Box Data")
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
    allow_rotation = st.checkbox("Allow horizontal rotation", value=True)

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.dataframe(df)

    # Assign color if missing
    if "color" not in df.columns:
        import matplotlib.colors as mcolors
        unique_parts = df["Part No"].unique()
        color_map = dict(zip(unique_parts, list(mcolors.CSS4_COLORS.values())[:len(unique_parts)]))
        df["color"] = df["Part No"].map(color_map)

    # Pack boxes
    boxes = df.to_dict(orient="records")
    placed_boxes = pack_boxes_on_pallets(boxes, STANDARD_PALLET_SIZE, MAX_PALLET_HEIGHT, allow_rotation=allow_rotation)

    if placed_boxes:
        used_L = max(b["x"] + b["L"] for b in placed_boxes)
        used_W = max(b["y"] + b["W"] for b in placed_boxes)
        used_H = max(b["z"] + b["H"] for b in placed_boxes) + STANDARD_PALLET_SIZE[2]

        st.subheader("📏 Pallet Output Dimensions")
        st.write(f"**Used Pallet Dimensions (L x W x H):** {used_L:.1f} cm × {used_W:.1f} cm × {used_H:.1f} cm")

        # 3D Visualization
        fig = go.Figure()
        for box in placed_boxes:
            fig.add_trace(go.Mesh3d(
                x=[box["x"], box["x"]+box["L"], box["x"]+box["L"], box["x"], box["x"], box["x"]+box["L"], box["x"]+box["L"], box["x"]],
                y=[box["y"], box["y"], box["y"]+box["W"], box["y"]+box["W"], box["y"], box["y"], box["y"]+box["W"], box["y"]+box["W"]],
                z=[box["z"], box["z"], box["z"], box["z"], box["z"]+box["H"], box["z"]+box["H"], box["z"]+box["H"], box["z"]+box["H"]],
                color=box["color"],
                opacity=0.8,
                showscale=False
            ))

        fig.update_layout(
            scene=dict(
                xaxis_title='Length (cm)',
                yaxis_title='Width (cm)',
                zaxis_title='Height (cm)',
                aspectmode="data"
            ),
            margin=dict(l=0, r=0, b=0, t=0),
            height=700
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No boxes could be placed on the pallet. Check your dimensions or stacking constraints.")
else:
    st.info("Please upload a CSV file with columns: Part No, Quantity, L, W, H")
