"""
Extract OpenFOAM simulation results into a unified HDF5 dataset.

Reads velocity (U), pressure (p), temperature (T), and CO2 fields from
each completed case and stores them in a single HDF5 file for ML training.
"""

import os
import glob
import json

import numpy as np
import h5py

try:
    from fluidfoam import readfield, readmesh
except ImportError:
    print("fluidfoam not installed. Run: pip install fluidfoam")
    raise


# Paths (override with env vars for cluster)
CASES_DIR = os.environ.get(
    "CASES_DIR", "/home/team-008/data/cfd_cases"
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR", "/home/team-008/data/cfd_dataset"
)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "airflow_dataset.h5")


def find_final_timestep(case_dir):
    """Find the latest time directory in an OpenFOAM case."""
    time_dirs = []
    for d in os.listdir(case_dir):
        full_path = os.path.join(case_dir, d)
        if not os.path.isdir(full_path):
            continue
        try:
            t = float(d)
            if t > 0:
                time_dirs.append((t, d))
        except ValueError:
            continue

    if not time_dirs:
        return None
    return max(time_dirs, key=lambda x: x[0])[1]


def extract_case(case_dir):
    """Extract all fields from a completed OpenFOAM case.

    Returns:
        dict with keys: coords, velocity, pressure, temperature, co2, params
        or None if the case is incomplete.
    """
    # Check if case completed
    if not os.path.exists(os.path.join(case_dir, ".completed")):
        return None

    final_time = find_final_timestep(case_dir)
    if final_time is None:
        print(f"  WARNING: No time directories in {case_dir}")
        return None

    try:
        # Read mesh coordinates
        x, y, z = readmesh(case_dir)

        # Read fields at final time step
        U = readfield(case_dir, final_time, "U")      # (3, n_cells)
        p = readfield(case_dir, final_time, "p")       # (n_cells,)
        T = readfield(case_dir, final_time, "T")       # (n_cells,)

        # CO2 may not exist in all cases
        try:
            CO2 = readfield(case_dir, final_time, "CO2")  # (n_cells,)
        except Exception:
            CO2 = np.zeros_like(p)

        # Read case parameters
        params_path = os.path.join(case_dir, "case_params.json")
        with open(params_path) as f:
            params = json.load(f)

        return {
            "coords": np.stack([x, y, z], axis=-1).astype(np.float32),
            "velocity": U.T.astype(np.float32),  # (n_cells, 3)
            "pressure": p.astype(np.float32),
            "temperature": T.astype(np.float32),
            "co2": CO2.astype(np.float32),
            "params": params,
        }

    except Exception as e:
        print(f"  ERROR extracting {case_dir}: {e}")
        return None


def flatten_params(params, prefix=""):
    """Flatten nested dict into string key-value pairs for HDF5 attrs."""
    flat = {}
    for k, v in params.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            flat.update(flatten_params(v, key))
        elif isinstance(v, list):
            flat[key] = json.dumps(v)
        else:
            flat[key] = v
    return flat


def build_dataset():
    """Build unified HDF5 dataset from all completed cases."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    case_dirs = sorted(glob.glob(os.path.join(CASES_DIR, "case_*")))
    print(f"Found {len(case_dirs)} case directories")

    # Also build a CSV index
    index_rows = []

    with h5py.File(OUTPUT_FILE, "w") as hf:
        extracted = 0
        for i, case_dir in enumerate(case_dirs):
            case_name = os.path.basename(case_dir)
            data = extract_case(case_dir)

            if data is None:
                continue

            grp = hf.create_group(case_name)
            grp.create_dataset("coords", data=data["coords"],
                               compression="gzip")
            grp.create_dataset("velocity", data=data["velocity"],
                               compression="gzip")
            grp.create_dataset("pressure", data=data["pressure"],
                               compression="gzip")
            grp.create_dataset("temperature", data=data["temperature"],
                               compression="gzip")
            grp.create_dataset("co2", data=data["co2"],
                               compression="gzip")

            # Store parameters as attributes
            flat_params = flatten_params(data["params"])
            for k, v in flat_params.items():
                try:
                    grp.attrs[k] = v
                except TypeError:
                    grp.attrs[k] = str(v)

            extracted += 1

            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(case_dirs)} "
                      f"({extracted} extracted)")

            # Index row
            p = data["params"]
            index_rows.append({
                "case_id": case_name,
                "n_cells": len(data["pressure"]),
                "ac_speed": p.get("ac", {}).get("speed"),
                "ac_temperature": p.get("ac", {}).get("temperature"),
                "window_open": p.get("window", {}).get("is_open"),
                "layout_id": p.get("furniture", {}).get("layout_id"),
                "ventilation_rate": p.get("ventilation", {}).get("rate"),
            })

    print(f"\nDataset saved: {OUTPUT_FILE}")
    print(f"Total cases extracted: {extracted}/{len(case_dirs)}")

    # Save CSV index
    import pandas as pd
    index_path = os.path.join(OUTPUT_DIR, "case_index.csv")
    pd.DataFrame(index_rows).to_csv(index_path, index=False)
    print(f"Case index: {index_path}")


if __name__ == "__main__":
    build_dataset()
