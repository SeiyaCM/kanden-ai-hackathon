"""
Prepare CFD dataset for NVIDIA Modulus (Physics-NeMo) training.

Reads the HDF5 dataset from Phase 1, normalizes fields, and splits
into train/val/test sets (80/10/10 by case).
"""

import os
import json

import numpy as np
import h5py


# Paths
DATASET_PATH = os.environ.get(
    "DATASET_PATH", "/home/team-008/data/cfd_dataset/airflow_dataset.h5"
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR", "/home/team-008/data/cfd_dataset/prepared"
)


def load_dataset(hdf5_path):
    """Load all cases from HDF5 into a list of dicts."""
    cases = []
    with h5py.File(hdf5_path, "r") as hf:
        for case_name in sorted(hf.keys()):
            grp = hf[case_name]
            case_data = {
                "case_id": case_name,
                "coords": grp["coords"][:],       # (n_cells, 3)
                "velocity": grp["velocity"][:],     # (n_cells, 3)
                "pressure": grp["pressure"][:],     # (n_cells,)
                "temperature": grp["temperature"][:],  # (n_cells,)
                "co2": grp["co2"][:],               # (n_cells,)
                # Condition parameters from attributes
                "ac_speed": float(grp.attrs.get("ac.speed", 2.0)),
                "ac_temperature": float(grp.attrs.get("ac.temperature", 20.0)),
                "window_open": float(grp.attrs.get("window.is_open", 0)),
                "layout_id": float(grp.attrs.get("furniture.layout_id", 0)),
                "ventilation_rate": float(grp.attrs.get("ventilation.rate", 0.05)),
            }
            cases.append(case_data)
    return cases


def compute_normalization(cases):
    """Compute MinMax normalization parameters across all cases."""
    # Collect all values
    all_coords = np.concatenate([c["coords"] for c in cases], axis=0)
    all_velocity = np.concatenate([c["velocity"] for c in cases], axis=0)
    all_pressure = np.concatenate([c["pressure"] for c in cases])
    all_temperature = np.concatenate([c["temperature"] for c in cases])
    all_co2 = np.concatenate([c["co2"] for c in cases])

    # Condition parameters
    ac_speeds = np.array([c["ac_speed"] for c in cases])
    ac_temps = np.array([c["ac_temperature"] for c in cases])
    vent_rates = np.array([c["ventilation_rate"] for c in cases])

    norm_params = {
        "coords_min": all_coords.min(axis=0).tolist(),
        "coords_max": all_coords.max(axis=0).tolist(),
        "velocity_min": all_velocity.min(axis=0).tolist(),
        "velocity_max": all_velocity.max(axis=0).tolist(),
        "pressure_min": float(all_pressure.min()),
        "pressure_max": float(all_pressure.max()),
        "temperature_min": float(all_temperature.min()),
        "temperature_max": float(all_temperature.max()),
        "co2_min": float(all_co2.min()),
        "co2_max": float(all_co2.max()),
        "ac_speed_min": float(ac_speeds.min()),
        "ac_speed_max": float(ac_speeds.max()),
        "ac_temperature_min": float(ac_temps.min()),
        "ac_temperature_max": float(ac_temps.max()),
        "ventilation_rate_min": float(vent_rates.min()),
        "ventilation_rate_max": float(vent_rates.max()),
    }
    return norm_params


def normalize(val, vmin, vmax):
    """MinMax normalize to [0, 1]."""
    r = vmax - vmin
    if isinstance(r, (list, np.ndarray)):
        r = np.array(r)
        r[r == 0] = 1.0
    elif r == 0:
        r = 1.0
    return (val - vmin) / r


def case_to_arrays(case, norm):
    """Convert a single case to normalized input/output arrays.

    Input: (x, y, z, ac_speed, ac_temp, window_open, layout_id, ventilation_rate)
    Output: (u, v, w, p, T, CO2)
    """
    n_cells = len(case["pressure"])

    # Normalize spatial coordinates
    coords_norm = normalize(
        case["coords"],
        np.array(norm["coords_min"]),
        np.array(norm["coords_max"]),
    )

    # Normalize condition parameters (broadcast to n_cells)
    ac_speed_norm = normalize(
        case["ac_speed"], norm["ac_speed_min"], norm["ac_speed_max"]
    )
    ac_temp_norm = normalize(
        case["ac_temperature"], norm["ac_temperature_min"], norm["ac_temperature_max"]
    )
    window_open = case["window_open"]  # already 0 or 1
    layout_id = case["layout_id"] / 2.0  # normalize to [0, 1] for 3 layouts
    vent_rate_norm = normalize(
        case["ventilation_rate"],
        norm["ventilation_rate_min"],
        norm["ventilation_rate_max"],
    )

    # Build input array: (n_cells, 8)
    conditions = np.full((n_cells, 5), [
        ac_speed_norm, ac_temp_norm, window_open, layout_id, vent_rate_norm
    ], dtype=np.float32)

    inputs = np.hstack([coords_norm, conditions]).astype(np.float32)

    # Normalize outputs
    vel_norm = normalize(
        case["velocity"],
        np.array(norm["velocity_min"]),
        np.array(norm["velocity_max"]),
    )
    p_norm = normalize(
        case["pressure"], norm["pressure_min"], norm["pressure_max"]
    )
    t_norm = normalize(
        case["temperature"], norm["temperature_min"], norm["temperature_max"]
    )
    co2_norm = normalize(
        case["co2"], norm["co2_min"], norm["co2_max"]
    )

    outputs = np.column_stack([
        vel_norm,                    # (n_cells, 3)
        p_norm.reshape(-1, 1),       # (n_cells, 1)
        t_norm.reshape(-1, 1),       # (n_cells, 1)
        co2_norm.reshape(-1, 1),     # (n_cells, 1)
    ]).astype(np.float32)

    return inputs, outputs


def split_cases(cases, train_ratio=0.8, val_ratio=0.1):
    """Split cases into train/val/test sets."""
    n = len(cases)
    indices = np.random.RandomState(42).permutation(n)

    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_train + n_val]
    test_idx = indices[n_train + n_val:]

    return (
        [cases[i] for i in train_idx],
        [cases[i] for i in val_idx],
        [cases[i] for i in test_idx],
    )


def save_split(cases, norm, split_name, output_dir):
    """Save a dataset split as numpy arrays."""
    if not cases:
        print(f"  {split_name}: no cases, skipping")
        return

    all_inputs = []
    all_outputs = []

    for case in cases:
        inp, out = case_to_arrays(case, norm)
        all_inputs.append(inp)
        all_outputs.append(out)

    inputs = np.concatenate(all_inputs, axis=0)
    outputs = np.concatenate(all_outputs, axis=0)

    split_dir = os.path.join(output_dir, split_name)
    os.makedirs(split_dir, exist_ok=True)

    np.save(os.path.join(split_dir, "inputs.npy"), inputs)
    np.save(os.path.join(split_dir, "outputs.npy"), outputs)

    print(f"  {split_name}: {len(cases)} cases, "
          f"{len(inputs)} total points, "
          f"inputs {inputs.shape}, outputs {outputs.shape}")


def main():
    print(f"Loading dataset: {DATASET_PATH}")
    cases = load_dataset(DATASET_PATH)
    print(f"Loaded {len(cases)} cases")

    print("Computing normalization parameters...")
    norm = compute_normalization(cases)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    norm_path = os.path.join(OUTPUT_DIR, "normalization.json")
    with open(norm_path, "w") as f:
        json.dump(norm, f, indent=2)
    print(f"Saved normalization: {norm_path}")

    print("Splitting dataset...")
    train, val, test = split_cases(cases)

    print("Saving splits...")
    save_split(train, norm, "train", OUTPUT_DIR)
    save_split(val, norm, "val", OUTPUT_DIR)
    save_split(test, norm, "test", OUTPUT_DIR)

    print(f"\nPrepared dataset saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
