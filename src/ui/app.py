from .panels import ControlPanel, ParameterPanel, ResultsPanel, StatusBar

from src.core.constants import \
    WINDOW_SIZES, FRAME_PAYLOADS, RUNS_PER_CONFIG, FILE_SIZE
from src.core.types import SimulationConfig
from src.core.engine import Simulation
from src.core.worker import run_single_simulation

import os
import tkinter as tk
from tkinter import ttk
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed


class App(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("ARQ Protocol Simulator")
        self.geometry("600x500")
        self.minsize(500, 400)

        self.running = False
        self.stop_requested = False
        self._executor = None

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=(0, 10))

        self.params = ParameterPanel(top_frame)
        self.params.pack(side="left", fill="y")

        self.controls = ControlPanel(
            top_frame,
            on_run=self._on_run_single,
            on_batch=self._on_run_batch,
            on_stop=self._on_stop
        )
        self.controls.pack(side="right", anchor="n")

        self.results = ResultsPanel(main_frame)
        self.results.pack(fill="both", expand=True)

        self.status = StatusBar(main_frame)
        self.status.pack(fill="x", pady=(10, 0))

    def _on_run_single(self):
        if self.running:
            return

        self.running = True
        self.stop_requested = False
        self.controls.set_running(True)
        self.status.set_status("Running simulation...")

        config = self.params.get_config()
        thread = threading.Thread(target=self._run_simulation, args=(config,))
        thread.daemon = True
        thread.start()

    def _on_run_batch(self):
        if self.running:
            return

        self.running = True
        self.stop_requested = False
        self.controls.set_running(True)
        self.results.clear()

        thread = threading.Thread(target=self._run_batch_parallel)
        thread.daemon = True
        thread.start()

    def _on_stop(self):
        self.stop_requested = True
        self.status.set_status("Stopping...")
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_simulation(self, config: SimulationConfig):
        try:

            def progress_cb(progress: float, msg: str):
                self.after(0, lambda: self.status.set_status(msg, progress))

            result = run_single_simulation(config, progress_cb=progress_cb)

            self.after(0, lambda: self.results.add_result(result))
            self.after(0, lambda: self.status.set_status("Complete", 1.0))

        except Exception as e:
            self.after(0, lambda e=e: self.status.set_status(f"Error: {e}"))

        finally:
            self.after(0, self._finish_run)

    def _run_batch_parallel(self):
        tasks = []
        for w in WINDOW_SIZES:
            for p in FRAME_PAYLOADS:
                for seed in range(RUNS_PER_CONFIG):
                    tasks.append((w, p, seed))

        total = len(tasks)
        completed = 0
        num_workers = max(1, (os.cpu_count() or 0) - 1)

        self.status.set_status(f"Starting batch ({num_workers} workers)...")

        try:
            self._executor = ProcessPoolExecutor(max_workers=num_workers)
            futures = {
                self._executor.submit(run_single_simulation, task): task
                for task in tasks
            }

            for future in as_completed(futures):
                if self.stop_requested:
                    break

                try:
                    result = future.result()
                    self.after(0, lambda r=result: self.results.add_result(r))
                except Exception:
                    pass

                completed += 1
                progress = completed / total
                self.after(0, lambda p=progress, c=completed, t=total:
                           self.status.set_status(f"Run {c}/{t}", p))

            if not self.stop_requested:
                self.after(0,
                           lambda: self.status.set_status("Batch complete",
                                                          1.0))

        except Exception as e:
            self.after(0, lambda e=e: self.status.set_status(f"Error: {e}"))

        finally:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
            self.after(0, self._finish_run)

    def _finish_run(self):
        self.running = False
        self.controls.set_running(False)
