"""Optional tkinter front end to launcher.py. Importing this module needs no display or tkinter.

SettingsModel is headless. Commands are argv lists for the existing CLI; no build, install, settings validation,
game-start or crash-watch implementation lives here. Tk and OS folder opening are used only after opening the UI.
"""
import os
import queue
import subprocess
import sys
import threading

from . import settings


def controls():
    """The widget descriptions come from the same specification as `settings --show`."""
    return [{"key": key, "label": settings.LABELS[key], "default": default, "cost": cost,
             "kind": "bool" if kind is bool else "choice" if isinstance(kind, tuple) else "text",
             "choices": kind if isinstance(kind, tuple) else ()}
            for key, default, kind, cost in settings.SPEC]


class SettingsModel:
    def __init__(self, launcher, path):
        self.launcher = os.path.abspath(launcher)
        self.path = os.path.abspath(path)
        self.reload()

    def reload(self):
        self.saved = settings.load(self.path)

    def values(self, raw):
        if set(raw) != set(settings.KEYS):
            raise ValueError("The settings fields do not match the launcher's settings specification")
        return {key: settings.coerce(key, raw[key]) for key in settings.KEYS}

    def command(self, action, raw=None, *, recipe="", overrides=(), fo4_data=(), starfield="", pids=None,
                windows=None):
        argv = [sys.executable, "-I", "-u", self.launcher]
        if action == "save":
            values = self.values(raw)
            pairs = [f"{key}={str(value).lower() if isinstance(value, bool) else value}"
                     for key, value in values.items() if value != self.saved[key]]
            # Do not even open a file for writing on an unchanged Save (including a missing settings file).
            if not pairs:
                return None
            return argv + ["settings", "--settings", self.path] + [a for p in pairs for a in ("--set", p)]
        if action == "status":
            if not recipe:
                raise ValueError("Choose a build recipe first")
            return argv + ["status", recipe] + [a for p in overrides for a in ("--set", p)]
        if action == "detect":
            if not fo4_data or not starfield:
                raise ValueError("Choose the Fallout 4 Data folder and Starfield folder first")
            argv += ["detect", "--starfield", starfield]
            argv += [a for path in fo4_data for a in ("--fo4-data", path)]
            if self.saved["my_games"]:
                argv += ["--my-games", self.saved["my_games"]]
            return argv  # no --report or other output argument: the status panes are read-only
        if action == "play":
            reason = self.play_reason(raw, starfield, pids, windows=windows)
            if reason:
                raise ValueError(reason)
            try:
                current = settings.load(self.path)
            except OSError as e:
                raise ValueError(f"Cannot read saved settings: {e}") from None
            if current != self.saved:
                raise ValueError("Settings changed outside this window; reload settings before playing")
            return argv + ["play", "--settings", self.path, "--starfield", starfield]
        raise ValueError(f"Unknown window action {action!r}")

    def play_reason(self, raw, starfield, pids, *, windows=None):
        if windows is None:
            windows = os.name == "nt"
        if not windows:
            return "Playing is available on Windows"
        if pids is None:
            return "Checking whether Starfield is running"
        if pids:
            return "Starfield is already running (PID " + ", ".join(map(str, pids)) + ")"
        try:
            values = self.values(raw)
        except ValueError as e:
            return str(e)
        problems = settings.problems(values)
        if problems:
            return "; ".join(problems)
        if values != self.saved:
            return "Save the changed settings before playing"
        if not starfield:
            return "Choose the Starfield folder first"
        return ""


def run_command(argv, on_line, *, popen=subprocess.Popen):
    """Stream a single existing CLI command; the UI calls this on a worker, never on the Tk thread."""
    repo = os.path.dirname(os.path.dirname(argv[3]))
    with popen(argv, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               text=True, errors="replace", bufsize=1) as proc:
        for line in proc.stdout:
            on_line(line)
        return proc.wait()


def launch(launcher, path, *, recipe="", overrides=(), fo4_data=(), starfield=""):
    # The CLI's --help and every other subcommand work even when Python has no tkinter or display.
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        from tkinter.scrolledtext import ScrolledText
    except ImportError:
        raise ValueError("The launcher window needs Python's tkinter; the command-line launcher still works") from None
    model = SettingsModel(launcher, path)
    try:
        root = tk.Tk()
    except tk.TclError as e:
        raise ValueError(f"Cannot open the launcher window: {e}") from None

    class Window:
        def __init__(self):
            self.events = queue.Queue()
            self.busy, self.closed = False, False
            self.pids, self.process_error = None, ""
            self.widgets, self.vars = [], {}
            root.title("Fallout 4 to Starfield Launcher")
            root.geometry("980x780")
            root.minsize(760, 580)
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)
            notebook = ttk.Notebook(root)
            notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            status = ttk.Frame(notebook, padding=12)
            config = ttk.Frame(notebook)
            logs = ttk.Frame(notebook, padding=12)
            for frame, label in ((status, "Status"), (config, "Settings"), (logs, "Command log")):
                notebook.add(frame, text=label)
            status.columnconfigure(1, weight=1)
            self.recipe = tk.StringVar(value=recipe)
            self.starfield = tk.StringVar(value=starfield)
            for row, label, variable, directory in ((0, "Build recipe", self.recipe, False),
                                                     (1, "Starfield folder", self.starfield, True)):
                ttk.Label(status, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
                ttk.Entry(status, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=4)
                def browse(var=variable, folder=directory):
                    choice = filedialog.askdirectory() if folder else filedialog.askopenfilename()
                    if choice:
                        var.set(choice)
                ttk.Button(status, text="Browse…", command=browse).grid(row=row, column=2)
            ttk.Label(status, text="Fallout 4 Data folders\n(one per line)").grid(row=2, column=0, sticky="nw", padx=4)
            self.data = tk.Text(status, height=2, width=36)
            self.data.insert("1.0", "\n".join(fo4_data))
            self.data.grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
            actions = ttk.Frame(status)
            actions.grid(row=3, column=0, columnspan=3, sticky="w", pady=8)
            for action, label in (("status", "Build status"), ("detect", "Check installation")):
                button = ttk.Button(actions, text=label, command=lambda a=action: self.start(a))
                button.pack(side="left", padx=4)
                self.widgets.append((button, "normal"))
            self.report = ScrolledText(status, height=12, wrap="word", state="disabled")
            self.report.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=8)
            status.rowconfigure(4, weight=1)

            # Captions stay beside their control, including on displays smaller than the full settings list.
            canvas = tk.Canvas(config, highlightthickness=0)
            scroll = ttk.Scrollbar(config, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            form = ttk.Frame(canvas, padding=12)
            item = canvas.create_window((0, 0), window=form, anchor="nw")
            form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
            form.columnconfigure(1, weight=1)
            ttk.Label(form, text="Settings file: " + model.path, wraplength=660).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
            for i, spec in enumerate(controls()):
                key, kind = spec["key"], spec["kind"]
                var = tk.BooleanVar(value=model.saved[key]) if kind == "bool" else tk.StringVar(value=model.saved[key])
                self.vars[key] = var
                ttk.Label(form, text=spec["label"]).grid(row=1 + 2*i, column=0, sticky="w", padx=(0, 8))
                if kind == "bool":
                    widget = ttk.Checkbutton(form, variable=var)
                elif kind == "choice":
                    widget = ttk.Combobox(form, textvariable=var, values=spec["choices"], state="readonly")
                else:
                    widget = ttk.Entry(form, textvariable=var)
                widget.grid(row=1 + 2*i, column=1, sticky="ew")
                self.widgets.append((widget, "readonly" if kind == "choice" else "normal"))
                ttk.Label(form, text=spec["cost"], wraplength=660, foreground="#555555").grid(
                    row=2 + 2*i, column=0, columnspan=2, sticky="w", pady=(2, 12))

            logs.rowconfigure(0, weight=1)
            logs.columnconfigure(0, weight=1)
            self.log = ScrolledText(logs, wrap="word", state="disabled")
            self.log.grid(row=0, column=0, sticky="nsew")
            ttk.Label(logs, text="Recent command output. The crash watcher keeps its own log in the dump folder.").grid(
                row=1, column=0, sticky="w", pady=6)
            ttk.Button(logs, text="Open crash log folder", command=self.open_logs).grid(row=2, column=0, sticky="w")
            footer = ttk.Frame(root, padding=(12, 0, 12, 12))
            footer.grid(row=1, column=0, sticky="ew")
            footer.columnconfigure(0, weight=1)
            self.message = tk.StringVar(value="Choose a recipe for build status, or the game folders for installation checks.")
            ttk.Label(footer, textvariable=self.message, wraplength=660).grid(row=0, column=0, sticky="w")
            self.reason = tk.StringVar()
            ttk.Label(footer, textvariable=self.reason, wraplength=660).grid(row=1, column=0, sticky="w")
            self.play = ttk.Button(footer, text="Play", command=lambda: self.start("play"))
            self.play.grid(row=0, column=1, rowspan=2, padx=8)
            save = ttk.Button(footer, text="Save settings", command=lambda: self.start("save"))
            save.grid(row=0, column=2, rowspan=2)
            self.widgets.append((save, "normal"))
            reload_button = ttk.Button(footer, text="Reload settings", command=self.reload_settings)
            reload_button.grid(row=2, column=2, pady=(6, 0))
            self.widgets.append((reload_button, "normal"))
            for var in list(self.vars.values()) + [self.starfield]:
                var.trace_add("write", lambda *_args: self.refresh_play())
            root.protocol("WM_DELETE_WINDOW", self.close)
            self.refresh_play()
            root.after(75, self.drain)
            self.poll_processes()

        def raw(self):
            return {key: var.get() for key, var in self.vars.items()}

        def reload_settings(self):
            try:
                model.reload()
                for key, var in self.vars.items():
                    var.set(model.saved[key])
                self.message.set("Reloaded saved settings")
            except (OSError, ValueError) as e:
                self.message.set(str(e))
            self.refresh_play()

        def refresh_play(self):
            reason = "An operation is still running" if self.busy else self.process_error or model.play_reason(
                self.raw(), self.starfield.get(), self.pids)
            self.reason.set(reason)
            self.play.configure(state="disabled" if reason else "normal")

        def append(self, widget, text):
            widget.configure(state="normal")
            widget.insert("end", text)
            # Bound the window's memory; the underlying commands keep their own full recorded logs.
            lines = int(widget.index("end-1c").split(".")[0])
            if lines > 2000:
                widget.delete("1.0", f"{lines - 2000}.0")
            widget.see("end")
            widget.configure(state="disabled")

        def start(self, action):
            if self.busy:
                return
            try:
                argv = model.command(action, self.raw(), recipe=self.recipe.get(), overrides=overrides,
                                     fo4_data=[p.strip() for p in self.data.get("1.0", "end").splitlines() if p.strip()],
                                     starfield=self.starfield.get(), pids=None if self.process_error else self.pids)
            except ValueError as e:
                self.message.set(str(e))
                return
            if argv is None:
                self.message.set("Settings unchanged; nothing written")
                return
            self.busy, self.action = True, action
            for widget, _state in self.widgets:
                widget.configure(state="disabled")
            self.message.set(f"Running {action}…")
            self.refresh_play()
            self.append(self.log, "\n> " + subprocess.list2cmdline(argv) + "\n")
            if action in ("status", "detect"):
                self.report.configure(state="normal")
                self.report.delete("1.0", "end")
                self.report.configure(state="disabled")
            def work():
                try:
                    rc = run_command(argv, lambda line: self.events.put(("line", line)))
                    self.events.put(("done", rc))
                except Exception as e:
                    self.events.put(("error", str(e)))
            threading.Thread(target=work, daemon=True).start()

        def drain(self):
            if self.closed:
                return
            while True:
                try:
                    kind, value = self.events.get_nowait()
                except queue.Empty:
                    break
                if kind == "processes":
                    self.pids, self.process_error = value, ""
                elif kind == "process_error":
                    self.pids, self.process_error = None, "Cannot check game processes: " + value
                elif kind == "line":
                    self.append(self.log, value)
                    if self.action in ("status", "detect"):
                        self.append(self.report, value)
                else:
                    self.busy = False
                    self.message.set(f"{self.action} finished (exit {value})" if kind == "done" else value)
                    for widget, state in self.widgets:
                        widget.configure(state=state)
                    if kind == "done" and value == 0 and self.action == "save":
                        try:
                            model.reload()
                            for key, var in self.vars.items():
                                var.set(model.saved[key])
                        except (OSError, ValueError) as e:
                            self.message.set(str(e))
                self.refresh_play()
            root.after(75, self.drain)

        def poll_processes(self):
            if self.closed:
                return
            def read():
                try:
                    from .crashwatch import System
                    self.events.put(("processes", System().pids()))
                except Exception as e:
                    self.events.put(("process_error", str(e)))
            threading.Thread(target=read, daemon=True).start()
            root.after(3000, self.poll_processes)

        def open_logs(self):
            folder = model.saved["crash_watch.folder"]
            if not folder or not os.path.isdir(folder):
                self.message.set("Set and save an existing dump folder first")
                return
            try:
                if os.name == "nt":
                    os.startfile(folder)
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
            except OSError as e:
                self.message.set(str(e))

        def close(self):
            if self.busy:
                messagebox.showinfo("Operation still running", "Keep this window open until the command finishes. "
                                    "Play follows the game and crash watcher until they finish.")
                return
            self.closed = True
            root.destroy()

    Window()
    root.mainloop()
    return 0
