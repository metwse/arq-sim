import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    """Status bar with progress indicator."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=5)

        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)

        ttk.Label(self, textvariable=self.status_var).pack(
            side="left", padx=5
        )

        self.progress = ttk.Progressbar(
            self, variable=self.progress_var, length=200
        )
        self.progress.pack(side="right", padx=5)

    def set_status(self, text: str, progress: float = 0.0):
        self.status_var.set(text)
        self.progress_var.set(progress * 100)
