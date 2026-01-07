from src.core.types import SimulationResult

import tkinter as tk
from tkinter import ttk


class ResultsPanel(ttk.LabelFrame):
    """Panel displaying simulation results."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, text="Results", padding=10)

        self.tree = ttk.Treeview(self, columns=(
            "window", "payload", "goodput", "retx", "time"
        ), show="headings", height=10)

        self.tree.heading("window", text="W")
        self.tree.heading("payload", text="L")
        self.tree.heading("goodput", text="Goodput (B/s)")
        self.tree.heading("retx", text="Retx")
        self.tree.heading("time", text="Time (s)")

        self.tree.column("window", width=50)
        self.tree.column("payload", width=60)
        self.tree.column("goodput", width=100)
        self.tree.column("retx", width=50)
        self.tree.column("time", width=80)

        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def add_result(self, result: SimulationResult):
        self.tree.insert("", "end", values=(
            result['window_size'],
            result['frame_payload_size'],
            f"{result['goodput']:.0f}",
            result['retransmissions'],
            f"{result['total_time']:.3f}"
        ))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
