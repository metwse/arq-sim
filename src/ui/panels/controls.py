from typing import Callable
import tkinter as tk
from tkinter import ttk


class ControlPanel(ttk.Frame):
    """Panel with simulation control buttons."""

    def __init__(self, parent: tk.Widget,
                 on_run: Callable, on_batch: Callable, on_stop: Callable):
        super().__init__(parent, padding=10)

        self.run_btn = ttk.Button(self, text="Run Single", command=on_run)
        self.run_btn.pack(side="left", padx=5)

        self.batch_btn = ttk.Button(self, text="Run Batch", command=on_batch)
        self.batch_btn.pack(side="left", padx=5)

        self.stop_btn = ttk.Button(self, text="Stop", command=on_stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=5)

    def set_running(self, running: bool):
        state = "disabled" if running else "normal"
        self.run_btn.config(state=state)
        self.batch_btn.config(state=state)
        self.stop_btn.config(state="normal" if running else "disabled")
