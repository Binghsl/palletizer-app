import streamlit as st
import pandas as pd
import numpy as np
from itertools import permutations

st.set_page_config(page_title="📦 Multi-Box Palletizer", layout="wide")
st.title("📦 Multi-Box Palletizer (Standard Pallet)")

st.markdown("""
Enter up to 10 box types with their quantity, dimensions, and rotation allowed.
The app calculates how to optimally stack boxes on standard pallets (default 120×100×150 cm).
""")

# Pallet config
st.sidebar.header("🧱 Pallet Settings")
pallet_length = st.sidebar.number_input("Pallet Length (cm)", min_value=50.0, value=120.0)
pallet_width = st.sidebar.number_input("Pallet Width (cm)", min_value=50.0, value=100.0)
max_pallet_height = st.sidebar.number_input("Max Pallet Height (cm)", min_value=50.0, value=150.0)

st.sidebar.markdown("---")
st.sidebar.markdown("**Rotation Allowed per Box?**")
default_rotation = st.sidebar.checkbox("Allow rotation globally (applies to all boxes)", value=True)

# Box input count
box_count = st.number_input("Number of Box Types (max 10)", min_value=1, max_value=10, value=3)

# Prepare default dataframe for box inputs
default_data = [{
    "Box Name": f"Box {i+1}",
    "Length (cm)": 30,
    "Width (cm)": 20,
    "Height (cm)": 15,
    "Quantity": 100,
    "Allow Rotation": default_rotation
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
