import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import box as shapely_box

# --- Constants ---
STANDARD_PALLET_SIZE = (120, 100, 15)  # Pallet Length, Width, Base Height (cm)
MAX_PALLET_HEIGHT = 180  # Max total pallet height (cm), including base

# --- Packing logic ---
def pack_boxes_on_pallets(boxes_df, pallet_size=STANDARD_PALLET_SIZE, max_height_cm=MAX_PALLET_HEIGHT, allow_rotation=True):
    placed_boxes = []
    remaining_boxes = []

    # Convert DataFrame rows to list of boxes repeated by quantity
    all_boxes = []
    for _, row in boxes_df.iterrows():
        qty = int(row["Quantity"])
        for _ in range(qty):
            all_boxes.append({
                "Part No": row["Part No"],
                "L": row["Length (cm)"],
                "W": row["Width (cm)"],
                "H": row["Height (cm)"],
                "color": row.get("color", "#636EFA")  # default Plotly blue
            })

    pallet_L, pallet_W, pallet_base_H = pallet_size
    max_stack_height = max_height_cm - pallet_base_H

    z_cursor = 0  # height cursor - current layer bottom z

    def can_place(new_box, placed, pallet_L, pallet_W):
        new_shape = shapely_box(
            new_box["x"],
            new_box["y"],
            new_box["x"] + new_box["L"],
            new_box["y"] + new_box["W"]
        )
        # Check pallet boundary
        if new_box["x"] + new_box["L"] > pallet_L or new_box["y"] + new_box["W"] > pallet_W:
            return False
        # Check overlap with placed boxes in layer
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

                    # Move cursor in Y if needed
                    if x_cursor >= pallet_L:
                        x_cursor = 0
                        y_cursor += trial_box["W"]
                        if y_cursor >= pallet_W:
                            # No more space in this layer
                            break
                    placed = True
                    break

            if not placed:
                remaining_boxes.append(box)

        if not placed_in_layer:
            # No boxes fit in this layer - stop packing
            break

        placed_boxes.extend(placed_in_layer)
        all_boxes = remaining_boxes
        z_cursor += row_max_height  # move height cursor for next layer

    return placed_boxes


# --- 3D Visualization ---
def visualize_pallet_3d(placed_boxes, pallet_size=STANDARD_PALLET_SIZE):
    pallet_L, pallet_W, pallet_base_H = pallet_size
    fig = go.Figure()

    # Pallet base
    fig.add_trace(go.Mesh3d(
        x=[0, pallet_L, pallet_L, 0, 0, pallet_L, pallet_L, 0],
        y=[0, 0, pallet_W, pallet_W, 0, 0, pallet_W, pallet_W],
        z=[0, 0, 0, 0, pallet_base_H, pallet_base_H, pallet_base_H, pallet_base_H],
        color="saddlebrown",
        opacity=0.5,
        name="Pallet Base",
        showscale=False
    ))

    # Boxes
    for box in placed_boxes:
        x, y, z = box["x"], box["y"], box["z"]
        L, W, H = box["L"], box["W"], box["H"]
        color = box.get("color", "#636EFA")

        fig.add_trace(go.Mesh3d(
            x=[x, x+L, x+L, x, x, x+L, x+L, x],
            y=[y, y, y+W, y+W, y, y, y+W, y+W],
            z=[z, z, z, z, z+H, z+H, z+H, z+H],
            color=color,
            opacity=0.8,
            name=box["Part No"],
            showscale=False
        ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="Length (cm)", range=[0, pallet_L]),
            yaxis=dict(title="Width (cm)", range=[0, pallet_W]),
            zaxis=dict(title="Height (cm)"),
            aspectmode="data"
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=700,
        showlegend=True,
        legend=dict(itemsizing="constant")
    )
    return fig


# --- Streamlit UI ---
st.set_page_config(page_title="📦 Multi-Part Palletizer with 3D", layout="wide")
st.title("📦 Multi-Part Palletizer with 3D Visualization")

st.markdown("""
Enter up to 10 different Part Numbers with their box dimensions and quantities.
Boxes will be packed layer-by-layer onto a standard pallet with no overlap.
""")

with st.sidebar:
    st.header("Pallet Settings")
    pallet_length = st.number_input("Pallet Length (cm)", min_value=50, max_value=200, value=STANDARD_PALLET_SIZE[0])
    pallet_width = st.number_input("Pallet Width (cm)", min_value=50, max_value=150, value=STANDARD_PALLET_SIZE[1])
    pallet_base_height = st.number_input("Pallet Base Height (cm)", min_value=5, max_value=30, value=STANDARD_PALLET_SIZE[2])
    max_pallet_height = st.number_input("Max Pallet Height (cm)", min_value=50, max_value=250, value=MAX_PALLET_HEIGHT)
    allow_rotation = st.checkbox("Allow horizontal rotation", value=True)

# Manual input form
st.header("Enter Box Data (Max 10 Part Numbers)")
max_rows = 10
part_nos = []
lengths = []
widths = []
heights = []
quantities = []

with st.form("box_input_form"):
    cols = st.columns(5)
    cols[0].markdown("**Part No**")
    cols[1].markdown("**Length (cm)**")
    cols[2].markdown("**Width (cm)**")
    cols[3].markdown("**Height (cm)**")
    cols[4].markdown("**Quantity**")

    for i in range(max_rows):
        c = st.columns(5)
        part_no = c[0].text_input(f"Part No {i+1}", key=f"pn_{i}")
        length = c[1].number_input(f"Length {i+1}", min_value=1.0, max_value=200.0, key=f"len_{i}")
        width = c[2].number_input(f"Width {i+1}", min_value=1.0, max_value=150.0, key=f"wid_{i}")
        height = c[3].number_input(f"Height {i+1}", min_value=1.0, max_value=150.0, key=f"hei_{i}")
        quantity = c[4].number_input(f"Quantity {i+1}", min_value=0, step=1, key=f"qty_{i}")

        part_nos.append(part_no)
        lengths.append(length)
        widths.append(width)
        heights.append(height)
        quantities.append(quantity)

    submitted = st.form_submit_button("Calculate Palletization")

if submitted:
    # Prepare DataFrame of boxes
    data = []
    for pn, l, w, h, q in zip(part_nos, lengths, widths, heights, quantities):
        if pn and q > 0:
            data.append({
                "Part No": pn,
                "Length (cm)": l,
                "Width (cm)": w,
                "Height (cm)": h,
                "Quantity": int(q),
                "color": None  # Optional: add a color assign later
            })
    if not data:
        st.error("Please enter at least one box with quantity > 0.")
    else:
        df_boxes = pd.DataFrame(data)

        # Assign colors for each part for visualization
        import matplotlib.colors as mcolors
        unique_parts = df_boxes["Part No"].unique()
        colors = list(mcolors.TABLEAU_COLORS.values())
        color_map = {pn: colors[i % len(colors)] for i, pn in enumerate(unique_parts)}
        df_boxes["color"] = df_boxes["Part No"].map(color_map)

        # Pack boxes
        pallet_size = (pallet_length, pallet_width, pallet_base_height)
        placed_boxes = pack_boxes_on_pallets(df_boxes, pallet_size, max_pallet_height, allow_rotation)

        if not placed_boxes:
            st.warning("No boxes could be placed on the pallet with current dimensions/constraints.")
        else:
            # Calculate used pallet dimensions from placed boxes
            used_length = max(box["x"] + box["L"] for box in placed_boxes)
            used_width = max(box["y"] + box["W"] for box in placed_boxes)
            used_height = max(box["z"] + box["H"] for box in placed_boxes) + pallet_base_height

            st.subheader("Used Pallet Dimensions (cm)")
            st.write(f"Length: {used_length:.1f} cm")
            st.write(f"Width: {used_width:.1f} cm")
            st.write(f"Height (including pallet base): {used_height:.1f} cm")

            # Show 3D pallet visualization
            fig = visualize_pallet_3d(placed_boxes, pallet_size)
            st.plotly_chart(fig, use_container_width=True)
