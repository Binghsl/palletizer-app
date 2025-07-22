import streamlit as st
import pandas as pd
import numpy as np
from itertools import product
import plotly.graph_objects as go
import random

# Pallet settings
PALLET_LENGTH = 120  # cm
PALLET_WIDTH = 100   # cm
PALLET_HEIGHT_LIMIT = 135  # box-only height in cm
PALLET_BASE_HEIGHT = 20  # cm pallet base

MAX_PARTS = 10

# Streamlit UI
st.set_page_config(layout="wide")
st.title("Multi-PN Palletizer with Height Optimization")

num_parts = st.number_input("How many Part Numbers to input (max 10)?", min_value=1, max_value=MAX_PARTS, value=3)

part_data = []

for i in range(num_parts):
    st.subheader(f"Part {i+1}")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        pn = st.text_input(f"Part Number {i+1}", key=f"pn_{i}")
    with col2:
        length = st.number_input(f"Length (cm) {i+1}", min_value=1, key=f"l_{i}")
    with col3:
        width = st.number_input(f"Width (cm) {i+1}", min_value=1, key=f"w_{i}")
    with col4:
        height = st.number_input(f"Height (cm) {i+1}", min_value=1, key=f"h_{i}")
    with col5:
        quantity = st.number_input(f"Quantity {i+1}", min_value=1, key=f"q_{i}")

    part_data.append({
        'pn': pn,
        'length': length,
        'width': width,
        'height': height,
        'quantity': quantity
    })

if st.button("Run Palletizing Simulation"):
    # Expand each part into individual boxes
    boxes = []
    for part in part_data:
        for _ in range(int(part['quantity'])):
            boxes.append({
                'pn': part['pn'],
                'length': part['length'],
                'width': part['width'],
                'height': part['height']
            })

    # Sort by height descending
    boxes = sorted(boxes, key=lambda x: (x['height'], x['length'], x['width']), reverse=True)

    pallets = []
    current_pallet = []
    current_height = 0
    used_area = np.zeros((PALLET_LENGTH, PALLET_WIDTH))

    def can_place(layer, l, w):
        if l > PALLET_LENGTH or w > PALLET_WIDTH:
            return False
        return True

    def place_layer(pallet, layer):
        pallet.append(layer)

    while boxes:
        current_pallet = []
        current_height = 0
        remaining_boxes = boxes.copy()

        while remaining_boxes:
            box = remaining_boxes[0]
            b_l, b_w, b_h = box['length'], box['width'], box['height']
            fits = can_place(current_pallet, b_l, b_w)

            if current_height + b_h <= PALLET_HEIGHT_LIMIT:
                current_pallet.append(box)
                current_height += b_h
                boxes.remove(box)
            else:
                break

        pallets.append(current_pallet)

    st.success(f"Total pallets needed: {len(pallets)}")

    # Visualize with Plotly 3D
    fig = go.Figure()
    colors = {}
    color_list = ["red", "green", "blue", "orange", "purple", "cyan", "yellow", "pink", "lime", "gray"]

    for p_idx, pallet in enumerate(pallets):
        z_offset = PALLET_BASE_HEIGHT
        x_offset = 0
        y_offset = 0
        layer_height = 0
        st.write(f"Pallet {p_idx+1}: {len(pallet)} boxes")

        for box in pallet:
            pn = box['pn']
            if pn not in colors:
                colors[pn] = color_list[len(colors) % len(color_list)]

            fig.add_trace(go.Mesh3d(
                x=[x_offset, x_offset + box['length'], x_offset + box['length'], x_offset, x_offset, x_offset + box['length'], x_offset + box['length'], x_offset],
                y=[y_offset, y_offset, y_offset + box['width'], y_offset + box['width'], y_offset, y_offset, y_offset + box['width'], y_offset + box['width']],
                z=[z_offset, z_offset, z_offset, z_offset, z_offset + box['height'], z_offset + box['height'], z_offset + box['height'], z_offset + box['height']],
                color=colors[pn],
                opacity=0.7,
                alphahull=0
            ))
            z_offset += box['height']  # Stack upward

    fig.update_layout(
        scene=dict(
            xaxis_title='Length (cm)',
            yaxis_title='Width (cm)',
            zaxis_title='Height (cm)'
        ),
        width=900,
        height=700,
        title="3D Pallet Simulation"
    )
    st.plotly_chart(fig)

    st.info(f"Each pallet base height: {PALLET_BASE_HEIGHT} cm. Box stacking limit: {PALLET_HEIGHT_LIMIT} cm.")
