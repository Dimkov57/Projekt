import threading
import queue
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import Project as project


class StationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gas Station Simulator - Simple GUI")

        self.log_queue = queue.Queue()
        self.orig_safe_print = project.safe_print

        # Controls frame
        frm = ttk.Frame(root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Number of pumps:").grid(row=0, column=0, sticky="w")
        self.pumps_var = tk.IntVar(value=getattr(project, 'NUM_PUMPS', 3))
        ttk.Entry(frm, textvariable=self.pumps_var, width=6).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="Max vehicles:").grid(row=0, column=2, sticky="w", padx=(10,0))
        self.max_var = tk.IntVar(value=10)
        ttk.Entry(frm, textvariable=self.max_var, width=6).grid(row=0, column=3, sticky="w")

        self.start_btn = ttk.Button(frm, text="Start", command=self.start_simulation)
        self.start_btn.grid(row=0, column=4, padx=(10,0))

        self.stop_btn = ttk.Button(frm, text="Stop", command=self.stop_simulation, state="disabled")
        self.stop_btn.grid(row=0, column=5, padx=(5,0))

        self.clear_btn = ttk.Button(frm, text="Clear Log", command=self.clear_log)
        self.clear_btn.grid(row=0, column=6, padx=(10,0))

        # Status and progress
        ttk.Label(frm, text="Status:").grid(row=1, column=0, sticky="w", pady=(6,0))
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(frm, textvariable=self.status_var).grid(row=1, column=1, columnspan=2, sticky="w", pady=(6,0))

        self.progress = ttk.Progressbar(frm, length=320, mode='determinate')
        self.progress.grid(row=1, column=3, columnspan=4, sticky="w", padx=(10,0), pady=(6,0))

        # Log area
        self.log = ScrolledText(root, height=20, width=100, state="disabled")
        self.log.grid(row=2, column=0, padx=10, pady=(0,10), sticky="nsew")

        root.rowconfigure(2, weight=1)
        root.columnconfigure(0, weight=1)

        self.manager = None
        self.updater_running = False

        # Start polling queue
        self.root.after(100, self.poll_log)

    def gui_safe_print(self, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        self.log_queue.put(text)
        # still keep original console output
        try:
            self.orig_safe_print(*args, **kwargs)
        except Exception:
            pass

    def poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", line + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        # Update status and progress
        try:
            if self.manager and self.manager.is_alive():
                max_veh = getattr(self.manager, 'max_vehicles', None)
                current = getattr(project, 'VEHICLE_COUNT', 0)
                if max_veh:
                    # configure progress bar maximum and value
                    try:
                        self.progress.configure(maximum=max_veh)
                        self.progress['value'] = current
                    except Exception:
                        pass
                    self.status_var.set(f"Running ({current}/{max_veh})")
                else:
                    self.status_var.set("Running")
            else:
                # not running
                self.status_var.set("Stopped")
        except Exception:
            pass

        self.root.after(100, self.poll_log)

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def start_simulation(self):
        if self.manager and self.manager.is_alive():
            return

        n_pumps = max(1, self.pumps_var.get())
        max_veh = max(1, self.max_var.get())

        # Patch module-level globals to match GUI settings
        project.NUM_PUMPS = n_pumps
        project.PUMPS_SEMAPHORE = threading.Semaphore(n_pumps)
        project.pump_status = [f"D{i+1}: Wolny" for i in range(n_pumps)]
        project.VEHICLE_COUNT = 0

        # Replace safe_print with GUI-aware function
        project.safe_print = self.gui_safe_print

        pumps = [project.Pump(i + 1) for i in range(n_pumps)]
        cashier = project.Cashier()

        self.manager = project.StationManager(pumps, cashier, max_vehicles=max_veh)
        self.manager.start()
        # disable controls while running
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="enabled")
        self.clear_btn.configure(state="disabled")
        # disable inputs
        for w in (self.pumps_var, self.max_var):
            pass
        try:
            # Attempt to disable entry widgets by walking children of frm
            for child in self.root.winfo_children()[0].winfo_children():
                if isinstance(child, ttk.Entry):
                    child.configure(state="disabled")
        except Exception:
            pass

    def stop_simulation(self):
        if not self.manager:
            return

        self.stop_btn.configure(state="disabled")
        self.gui_safe_print("Stopping simulation...")

        # Request manager to stop, then join it in a background thread so GUI stays responsive.
        def waiter(mgr, gui):
            try:
                mgr.stop()
                mgr.join()
            except Exception:
                pass
            # restore safe_print and re-enable controls on main thread
            def finish():
                project.safe_print = self.orig_safe_print
                self.start_btn.configure(state="enabled")
                self.stop_btn.configure(state="disabled")
                self.clear_btn.configure(state="enabled")
                try:
                    for child in self.root.winfo_children()[0].winfo_children():
                        if isinstance(child, ttk.Entry):
                            child.configure(state="normal")
                except Exception:
                    pass
                self.manager = None

            self.root.after(0, finish)

        t = threading.Thread(target=waiter, args=(self.manager, self))
        t.daemon = True
        t.start()


def main():
    root = tk.Tk()
    app = StationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
