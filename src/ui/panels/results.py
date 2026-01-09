from src.core.types import SimulationResult

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import numpy as np
import matplotlib.pyplot as plt


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

        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", anchor="w", pady=(5, 0))

        export_btn = ttk.Button(button_frame, text="Export Results as CSV",
                                command=self._on_export)
        export_btn.pack(side="left", padx=(0, 5))

        heatmap_btn = ttk.Button(button_frame, text="Show Heatmap",
                                 command=self._on_heatmap)
        heatmap_btn.pack(side="left")

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.results = []

    def add_result(self, result: SimulationResult):
        self.tree.insert("", "end", values=(
            result['window_size'],
            result['frame_payload_size'],
            f"{result['goodput']:.0f}",
            result['retransmissions'],
            f"{result['total_time']:.3f}"
        ))

        self.results.append(result)

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.results = []

    def _get_sorted_results(self):
        """Sort results by window_size and frame_payload_size."""
        return sorted(self.results,
                      key=lambda r: (r['window_size'],
                                     r['frame_payload_size']))

    def _on_export(self):
        """Export results to CSV file."""
        if not self.results:
            messagebox.showwarning("No Data", "No results to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="arq_results.csv"
        )

        if not filename:
            return

        try:
            sorted_results = self._get_sorted_results()

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Window Size', 'Frame Payload Size', 'Goodput (B/s)',
                    'Retransmissions', 'Avg RTT (s)', 'Utilization',
                    'Total Time (s)'
                ])

                for result in sorted_results:
                    writer.writerow([
                        result['window_size'],
                        result['frame_payload_size'],
                        f"{result['goodput']:.2f}",
                        result['retransmissions'],
                        f"{result['avg_rtt']:.6f}",
                        f"{result['utilization']:.4f}",
                        f"{result['total_time']:.6f}"
                    ])

            messagebox.showinfo("Success", f"Results exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _on_heatmap(self):
        """Display goodput heatmap."""
        if not self.results:
            messagebox.showwarning("No Data", "No results to visualize.")
            return

        goodput_map = {}
        count_map = {}

        for result in self.results:
            key = (result['window_size'], result['frame_payload_size'])
            goodput_map[key] = goodput_map.get(key, 0) + result['goodput']
            count_map[key] = count_map.get(key, 0) + 1

        for key in goodput_map:
            goodput_map[key] /= count_map[key]

        window_sizes = sorted(set(r['window_size'] for r in self.results))
        payload_sizes = sorted(
            set(r['frame_payload_size'] for r in self.results))

        heatmap_data = np.zeros((len(payload_sizes), len(window_sizes)))

        for i, payload in enumerate(payload_sizes):
            for j, window in enumerate(window_sizes):
                key = (window, payload)
                if key in goodput_map:
                    heatmap_data[i, j] = goodput_map[key]
                else:
                    heatmap_data[i, j] = np.nan

        _, ax = plt.subplots(figsize=(10, 6))

        im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto')

        ax.set_xticks(range(len(window_sizes)))
        ax.set_yticks(range(len(payload_sizes)))
        ax.set_xticklabels(window_sizes)
        ax.set_yticklabels(payload_sizes)

        ax.set_xlabel('Window Size')
        ax.set_ylabel('Frame Payload Size (bytes)')
        ax.set_title('Average Goodput (B/s)')

        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Goodput (B/s)', rotation=270, labelpad=20)

        for i in range(len(payload_sizes)):
            for j in range(len(window_sizes)):
                if not np.isnan(heatmap_data[i, j]):
                    ax.text(j, i, f'{heatmap_data[i, j]:.0f}',
                            ha="center", va="center", color="black",
                            fontsize=8)

        plt.tight_layout()
        plt.show()
