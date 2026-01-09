from src.core.constants import WINDOW_SIZES, FRAME_PAYLOADS
from src.core.types import SimulationConfig

import tkinter as tk
from tkinter import ttk


class ParameterPanel(ttk.LabelFrame):
    """Panel for configuring simulation parameters."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, text="Parameters", padding=10)

        self.window_var = tk.StringVar(value=str(WINDOW_SIZES[2]))
        self.payload_var = tk.StringVar(value=str(FRAME_PAYLOADS[3]))
        self.seed_var = tk.StringVar(value="1")

        row = 0
        ttk.Label(self, text="Window Size:").grid(
            row=row, column=0, sticky="w", pady=2
        )
        window_combo = ttk.Combobox(
            self, textvariable=self.window_var,
            values=[str(w) for w in WINDOW_SIZES], width=10, state="readonly"
        )
        window_combo.grid(row=row, column=1, sticky="w", pady=2)

        row += 1
        ttk.Label(self, text="Frame Payload:").grid(
            row=row, column=0, sticky="w", pady=2
        )
        payload_combo = ttk.Combobox(
            self, textvariable=self.payload_var,
            values=[str(p) for p in FRAME_PAYLOADS], width=10, state="readonly"
        )
        payload_combo.grid(row=row, column=1, sticky="w", pady=2)

        row += 1
        ttk.Label(self, text="RNG Seed:").grid(
            row=row, column=0, sticky="w", pady=2
        )
        ttk.Entry(self, textvariable=self.seed_var, width=12).grid(
            row=row, column=1, sticky="w", pady=2
        )

    def get_config(self) -> SimulationConfig:
        return SimulationConfig(
            window_size=int(self.window_var.get()),
            frame_payload_size=int(self.payload_var.get()),
            seed=int(self.seed_var.get())
        )
