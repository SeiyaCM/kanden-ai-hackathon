"""
Room domain definition and parameter grid for CFD simulations.

Defines a 6m x 5m x 2.7m office room with parameterized conditions:
- AC wind speed and temperature
- Window open/close state
- Furniture layout (3 patterns)
- Ventilation rate
- Occupant count (heat + CO2 sources)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Tuple
import itertools
import json
import os


# --- Geometry Definitions ---

@dataclass
class RoomConfig:
    """Office room dimensions (meters)."""
    length: float = 6.0   # x-axis
    width: float = 5.0    # y-axis
    height: float = 2.7   # z-axis


@dataclass
class ACConfig:
    """Air conditioner (inlet) configuration."""
    # AC is mounted on the wall at x=0, centered in y, near ceiling
    position: Tuple[float, float, float] = (0.0, 2.5, 2.4)
    size: Tuple[float, float] = (0.8, 0.2)  # width(y) x height(z)
    direction: Tuple[float, float, float] = (1.0, 0.0, -0.3)  # blows inward & slightly down
    speed: float = 2.0      # m/s (parameterized)
    temperature: float = 20.0  # degrees C (parameterized)


@dataclass
class VentilationConfig:
    """Ventilation fan (outlet) configuration."""
    # Exhaust fan on the opposite wall (x=6.0), near ceiling
    position: Tuple[float, float, float] = (6.0, 2.5, 2.4)
    size: Tuple[float, float] = (0.3, 0.3)  # width(y) x height(z)
    rate: float = 0.05  # m^3/s (parameterized)


@dataclass
class WindowConfig:
    """Window configuration."""
    # Window on the y=5.0 wall
    position: Tuple[float, float, float] = (3.0, 5.0, 1.0)
    size: Tuple[float, float] = (1.2, 1.0)  # width(x) x height(z)
    is_open: bool = False  # parameterized


@dataclass
class DeskConfig:
    """Single desk with monitor."""
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # desk center (floor level)
    size: Tuple[float, float, float] = (1.2, 0.6, 0.75)  # length x depth x height


@dataclass
class HumanConfig:
    """Seated human (heat + CO2 source)."""
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # center at floor level
    radius: float = 0.2       # body radius (m)
    height: float = 1.2       # seated height (m)
    heat_output: float = 75.0  # Watts
    co2_rate: float = 0.005   # L/s CO2 exhalation


@dataclass
class FurnitureLayout:
    """A complete furniture arrangement."""
    layout_id: int
    desks: List[DeskConfig] = field(default_factory=list)
    humans: List[HumanConfig] = field(default_factory=list)


# --- Predefined Layouts ---

def _layout_0() -> FurnitureLayout:
    """Layout 0: 4 desks in 2x2 grid, 4 occupants."""
    desks = [
        DeskConfig(position=(1.5, 1.5, 0.0)),
        DeskConfig(position=(1.5, 3.5, 0.0)),
        DeskConfig(position=(4.5, 1.5, 0.0)),
        DeskConfig(position=(4.5, 3.5, 0.0)),
    ]
    humans = [
        HumanConfig(position=(1.5, 0.9, 0.0)),
        HumanConfig(position=(1.5, 2.9, 0.0)),
        HumanConfig(position=(4.5, 0.9, 0.0)),
        HumanConfig(position=(4.5, 2.9, 0.0)),
    ]
    return FurnitureLayout(layout_id=0, desks=desks, humans=humans)


def _layout_1() -> FurnitureLayout:
    """Layout 1: 3 desks in a row along x-axis, 3 occupants."""
    desks = [
        DeskConfig(position=(1.5, 2.5, 0.0)),
        DeskConfig(position=(3.0, 2.5, 0.0)),
        DeskConfig(position=(4.5, 2.5, 0.0)),
    ]
    humans = [
        HumanConfig(position=(1.5, 1.9, 0.0)),
        HumanConfig(position=(3.0, 1.9, 0.0)),
        HumanConfig(position=(4.5, 1.9, 0.0)),
    ]
    return FurnitureLayout(layout_id=1, desks=desks, humans=humans)


def _layout_2() -> FurnitureLayout:
    """Layout 2: 2 desks side by side, 2 occupants (small team)."""
    desks = [
        DeskConfig(position=(3.0, 1.5, 0.0)),
        DeskConfig(position=(3.0, 3.5, 0.0)),
    ]
    humans = [
        HumanConfig(position=(3.0, 0.9, 0.0)),
        HumanConfig(position=(3.0, 2.9, 0.0)),
    ]
    return FurnitureLayout(layout_id=2, desks=desks, humans=humans)


LAYOUTS = {
    0: _layout_0,
    1: _layout_1,
    2: _layout_2,
}


# --- Simulation Case ---

@dataclass
class SimulationCase:
    """A single parameterized CFD simulation case."""
    case_id: str
    room: RoomConfig
    ac: ACConfig
    window: WindowConfig
    furniture: FurnitureLayout
    ventilation: VentilationConfig
    ambient_temp: float = 30.0  # outside temperature (degrees C)

    def to_dict(self) -> dict:
        return asdict(self)


# --- Parameter Grid ---

# Parameterized values
AC_SPEEDS = [1.0, 3.0, 5.0]
AC_TEMPS = [20.0, 24.0, 28.0]
VENTILATION_RATES = [0.0, 0.05, 0.1]
WINDOW_STATES = [False, True]
LAYOUT_IDS = [0]


def generate_parameter_grid() -> List[SimulationCase]:
    """Generate all parameter combinations.

    Total cases: 3 * 3 * 3 * 2 * 1 = 54
    """
    cases = []
    case_idx = 0

    for ac_speed, ac_temp, vent_rate, window_open, layout_id in itertools.product(
        AC_SPEEDS, AC_TEMPS, VENTILATION_RATES, WINDOW_STATES, LAYOUT_IDS
    ):
        room = RoomConfig()
        ac = ACConfig(speed=ac_speed, temperature=ac_temp)
        window = WindowConfig(is_open=window_open)
        ventilation = VentilationConfig(rate=vent_rate)
        furniture = LAYOUTS[layout_id]()

        case = SimulationCase(
            case_id=f"case_{case_idx:04d}",
            room=room,
            ac=ac,
            window=window,
            furniture=furniture,
            ventilation=ventilation,
        )
        cases.append(case)
        case_idx += 1

    return cases


def save_case_list(cases: List[SimulationCase], output_dir: str):
    """Save case_list.txt and per-case case_params.json."""
    case_list_path = os.path.join(output_dir, "case_list.txt")
    with open(case_list_path, "w") as f:
        for case in cases:
            case_dir = os.path.join(output_dir, case.case_id)
            f.write(case_dir + "\n")

    for case in cases:
        case_dir = os.path.join(output_dir, case.case_id)
        os.makedirs(case_dir, exist_ok=True)
        params_path = os.path.join(case_dir, "case_params.json")
        with open(params_path, "w") as f:
            json.dump(case.to_dict(), f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    cases = generate_parameter_grid()
    print(f"Total cases: {len(cases)}")
    # Print first case as example
    print(json.dumps(cases[0].to_dict(), indent=2, ensure_ascii=False))
