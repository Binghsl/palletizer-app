import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from shapely.geometry import box as shapely_box
import matplotlib.colors as mcolors

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
                    "
