import os
import random
import re
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext
import tkinter.ttk as ttk
from typing import Optional, Tuple

# === CYBERPUNK COLOR PALETTE ===
BG_MAIN = "#050814"        # Deep near-black
BG_PANEL = "#0b1020"       # Dark panel
FG_TEXT = "#f5f5f5"        # Light text
NEON_PINK = "#ff00ff"
NEON_CYAN = "#00f5ff"
NEON_PURPLE = "#9b5cff"
NEON_ORANGE = "#ff8b3d"
BORDER_NEON = "#3dffb8"


def run_pytest(
    target_path: str,
    is_directory: bool,
    flag: Optional[str] = None,
) -> Tuple[str, str, int]:
    """
    Run 'python -m pytest' on the given file or directory.

    Returns:
        (stdout, stderr, return_code)
    """
    try:
        cmd = [sys.executable, "-m", "pytest"]

        if flag and flag.lower() != "normal":
            cmd.append(flag)

        cmd.append(target_path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
        )

        return result.stdout, result.stderr, result.returncode

    except Exception as exc:  # noqa: BLE001
        return "", f"Unexpected error running pytest: {exc}", 1


class PytestGUI(tk.Tk):
    """GUI app to pick a file/folder and run pytest with a neon cyberpunk theme."""

    def __init__(self) -> None:
        super().__init__()

        # === WINDOW SETUP ===
        self.title("CYBERTEST // pytest runner")
        self.geometry("1100x700")
        self.minsize(1000, 620)
        self.configure(bg=BG_MAIN)

        # State
        self.selected_path: Optional[str] = None
        self.is_directory: bool = False
        self.last_stdout: str = ""
        self.last_stderr: str = ""
        self.boot_in_progress: bool = True

        # Animation state
        self.scan_x: int = 0
        self.cursor_on: bool = True

        # Test counters
        self.tests_passed: int = 0
        self.tests_failed: int = 0
        self.tests_errors: int = 0
        self.tests_skipped: int = 0
        self.tests_total: int = 0

        # HUD values
        self.cpu_usage: int = 0
        self.ram_used_gb: float = 0.0
        self.ram_total_gb: float = 16.0

        # Last runs history: list of dicts containing summary + full output
        self.run_history: list[dict] = []

        # Configure ttk style for neon look
        self._configure_style()

        # Build UI
        self._create_widgets()

        # Disable select until boot completes
        self.select_button.config(state=tk.DISABLED, bg="#333333")

        # Start animations
        self.after(200, self._start_boot_sequence)
        self.after(600, self._animate_scanline)
        self.after(500, self._blink_cursor)
        self.after(800, self._update_hud)

    def _configure_style(self) -> None:
        """Configure ttk styles to match neon theme."""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Neon.TCombobox",
            fieldbackground=BG_PANEL,
            background=BG_PANEL,
            foreground=NEON_CYAN,
            bordercolor=NEON_PINK,
            lightcolor=NEON_PINK,
            darkcolor=BG_PANEL,
            arrowcolor=NEON_PINK,
            selectbackground=BG_PANEL,
            selectforeground=NEON_CYAN,
            padding=4,
        )

        style.map(
            "Neon.TCombobox",
            fieldbackground=[("active", BG_PANEL), ("readonly", BG_PANEL)],
            foreground=[("active", NEON_CYAN)],
            arrowcolor=[("active", NEON_ORANGE)],
        )

    def _neon_button(
        self,
        master: tk.Misc,
        text: str,
        command,
    ) -> tk.Button:
        """Helper to create a neon-styled button."""
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=NEON_PINK,
            fg=FG_TEXT,
            activebackground=NEON_PURPLE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            highlightthickness=0,
            font=("Segoe UI", 10, "bold"),
        )

    def _create_widgets(self) -> None:
        """Create and layout all widgets."""

        # === HEADER BAR ===
        header_frame = tk.Frame(self, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        title_label = tk.Label(
            header_frame,
            text="CYBERTEST // PYTEST RUNNER",
            fg=NEON_CYAN,
            bg=BG_MAIN,
            font=("Consolas", 18, "bold"),
        )
        title_label.pack(side=tk.LEFT, padx=(5, 20))

        subtitle_label = tk.Label(
            header_frame,
            text="INIT: diagnostics_online  •  by Lance Jepsen",
            fg=NEON_PURPLE,
            bg=BG_MAIN,
            font=("Consolas", 9),
        )
        subtitle_label.pack(side=tk.LEFT, pady=4)

        divider = tk.Frame(self, bg=BORDER_NEON, height=2)
        divider.pack(fill=tk.X, padx=10, pady=(0, 10))

        # === MODE (FILE VS FOLDER) PANEL ===
        mode_outer = tk.Frame(self, bg=BG_MAIN)
        mode_outer.pack(fill=tk.X, padx=10)

        mode_frame = tk.LabelFrame(
            mode_outer,
            text="  TARGET  ",
            bg=BG_PANEL,
            fg=NEON_ORANGE,
            bd=2,
            relief=tk.GROOVE,
            labelanchor="nw",
            font=("Consolas", 9, "bold"),
        )
        mode_frame.pack(fill=tk.X, pady=5)

        self.mode_var = tk.StringVar(value="file")

        file_radio = tk.Radiobutton(
            mode_frame,
            text="Single file",
            variable=self.mode_var,
            value="file",
            command=self._on_mode_change,
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_MAIN,
            activebackground=BG_PANEL,
            activeforeground=NEON_CYAN,
            font=("Segoe UI", 9),
        )
        folder_radio = tk.Radiobutton(
            mode_frame,
            text="Folder (auto-detect tests: test_*.py)",
            variable=self.mode_var,
            value="folder",
            command=self._on_mode_change,
            bg=BG_PANEL,
            fg=FG_TEXT,
            selectcolor=BG_MAIN,
            activebackground=BG_PANEL,
            activeforeground=NEON_CYAN,
            font=("Segoe UI", 9),
        )
        file_radio.pack(side=tk.LEFT, padx=10, pady=6)
        folder_radio.pack(side=tk.LEFT, padx=10, pady=6)

        # === CONTROL BAR (SELECT / RUN / FLAGS) ===
        control_outer = tk.Frame(self, bg=BG_MAIN)
        control_outer.pack(fill=tk.X, padx=10, pady=6)

        control_frame = tk.Frame(
            control_outer,
            bg=BG_PANEL,
            bd=2,
            relief=tk.GROOVE,
        )
        control_frame.pack(fill=tk.X)

        self.select_button = self._neon_button(
            control_frame,
            text="SELECT TARGET",
            command=self.select_path,
        )
        self.select_button.pack(side=tk.LEFT, padx=8, pady=8)

        self.run_button = self._neon_button(
            control_frame,
            text="RUN PYTEST",
            command=self.run_tests,
        )
        self.run_button.config(state=tk.DISABLED, bg="#555555")
        self.run_button.pack(side=tk.LEFT, padx=8, pady=8)

        flag_label = tk.Label(
            control_frame,
            text="pytest flags:",
            fg=NEON_CYAN,
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        flag_label.pack(side=tk.LEFT, padx=(24, 5))

        self.flag_var = tk.StringVar(value="Normal")
        self.flag_combo = ttk.Combobox(
            control_frame,
            textvariable=self.flag_var,
            state="readonly",
            width=10,
            style="Neon.TCombobox",
        )
        self.flag_combo["values"] = ("Normal", "-q", "-vv", "-x")
        self.flag_combo.current(0)
        self.flag_combo.pack(side=tk.LEFT, padx=6, pady=6)

        # === PATH LABEL ===
        self.path_label = tk.Label(
            self,
            text="// no target selected",
            fg="#8888aa",
            bg=BG_MAIN,
            anchor="w",
            font=("Consolas", 9),
        )
        self.path_label.pack(fill=tk.X, padx=14, pady=(4, 4))

        # === CENTRAL AREA: LEFT (OUTPUT) + RIGHT (HUD) ===
        center_outer = tk.Frame(self, bg=BG_MAIN)
        center_outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        # LEFT: output/terminal
        output_outer = tk.Frame(center_outer, bg=BG_MAIN)
        output_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        output_frame = tk.Frame(
            output_outer,
            bg=BG_PANEL,
            bd=2,
            relief=tk.GROOVE,
        )
        output_frame.pack(fill=tk.BOTH, expand=True)

        # Scanline canvas (animated)
        self.scan_canvas = tk.Canvas(
            output_frame,
            height=6,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.scan_canvas.pack(fill=tk.X, padx=4, pady=(4, 0))

        output_label = tk.Label(
            output_frame,
            text="TERMINAL FEED // pytest output",
            fg=NEON_PINK,
            bg=BG_PANEL,
            anchor="w",
            font=("Consolas", 9, "bold"),
        )
        output_label.pack(fill=tk.X, padx=6, pady=(2, 0))

        self.output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            bg="#050814",
            fg="#e0e0ff",
            insertbackground=NEON_CYAN,
            relief=tk.FLAT,
            bd=0,
            font=("Consolas", 10),
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # RIGHT: HUD + test summary + history
        hud_outer = tk.Frame(center_outer, bg=BG_MAIN)
        hud_outer.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        # SYSTEM HUD
        hud_frame = tk.Frame(
            hud_outer,
            bg=BG_PANEL,
            bd=2,
            relief=tk.GROOVE,
        )
        hud_frame.pack(fill=tk.X, pady=(0, 6))

        hud_title = tk.Label(
            hud_frame,
            text="SYSTEM HUD",
            fg=NEON_CYAN,
            bg=BG_PANEL,
            font=("Consolas", 10, "bold"),
        )
        hud_title.pack(anchor="w", padx=8, pady=(6, 2))

        self.cpu_label = tk.Label(
            hud_frame,
            text="CPU: -- %",
            fg=FG_TEXT,
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.cpu_label.pack(anchor="w", padx=12, pady=2)

        self.ram_label = tk.Label(
            hud_frame,
            text="RAM: -- / -- GB",
            fg=FG_TEXT,
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.ram_label.pack(anchor="w", padx=12, pady=(0, 8))

        self.cpu_bar = tk.Canvas(
            hud_frame,
            height=10,
            width=160,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.cpu_bar.pack(padx=12, pady=(0, 4))

        self.ram_bar = tk.Canvas(
            hud_frame,
            height=10,
            width=160,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0,
        )
        self.ram_bar.pack(padx=12, pady=(0, 8))

        # TEST SUMMARY + HISTORY PANEL
        summary_frame = tk.Frame(
            hud_outer,
            bg=BG_PANEL,
            bd=2,
            relief=tk.GROOVE,
        )
        summary_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        summary_title = tk.Label(
            summary_frame,
            text="TEST SUMMARY",
            fg=NEON_ORANGE,
            bg=BG_PANEL,
            font=("Consolas", 10, "bold"),
        )
        summary_title.pack(anchor="w", padx=8, pady=(6, 2))

        self.summary_total = tk.Label(
            summary_frame,
            text="Total: 0",
            fg=FG_TEXT,
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.summary_total.pack(anchor="w", padx=12, pady=2)

        self.summary_passed = tk.Label(
            summary_frame,
            text="Passed: 0",
            fg="#3dffb8",
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.summary_passed.pack(anchor="w", padx=12, pady=2)

        self.summary_failed = tk.Label(
            summary_frame,
            text="Failed: 0",
            fg="#ff5555",
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.summary_failed.pack(anchor="w", padx=12, pady=2)

        self.summary_errors = tk.Label(
            summary_frame,
            text="Errors: 0",
            fg="#ff8b3d",
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.summary_errors.pack(anchor="w", padx=12, pady=2)

        self.summary_skipped = tk.Label(
            summary_frame,
            text="Skipped: 0",
            fg="#cccc88",
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.summary_skipped.pack(anchor="w", padx=12, pady=2)

        summary_hint = tk.Label(
            summary_frame,
            text="// last run only",
            fg="#8888aa",
            bg=BG_PANEL,
            font=("Consolas", 8),
        )
        summary_hint.pack(anchor="w", padx=12, pady=(4, 4))

        # Last 5 runs history
        history_title = tk.Label(
            summary_frame,
            text="LAST 5 RUNS",
            fg=NEON_PINK,
            bg=BG_PANEL,
            font=("Consolas", 10, "bold"),
        )
        history_title.pack(anchor="w", padx=8, pady=(4, 2))

        self.history_listbox = tk.Listbox(
            summary_frame,
            height=5,
            bg="#050814",
            fg="#d0d0ff",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 8),
            selectbackground="#1b2238",
            selectforeground="#ffffff",
        )
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        # Bind click on history items
        self.history_listbox.bind("<<ListboxSelect>>", self._on_history_select)

        # === EXPORT BAR + STATUS ===
        export_outer = tk.Frame(self, bg=BG_MAIN)
        export_outer.pack(fill=tk.X, padx=10, pady=(0, 10))

        export_frame = tk.Frame(
            export_outer,
            bg=BG_PANEL,
            bd=2,
            relief=tk.GROOVE,
        )
        export_frame.pack(fill=tk.X)

        save_txt_button = self._neon_button(
            export_frame,
            text="EXPORT TXT",
            command=self.save_output_txt,
        )
        save_txt_button.pack(side=tk.LEFT, padx=8, pady=6)

        save_html_button = self._neon_button(
            export_frame,
            text="EXPORT HTML",
            command=self.save_output_html,
        )
        save_html_button.pack(side=tk.LEFT, padx=8, pady=6)

        self.cursor_label = tk.Label(
            export_frame,
            text="> BOOTING _",
            fg="#9999cc",
            bg=BG_PANEL,
            font=("Consolas", 9),
        )
        self.cursor_label.pack(side=tk.RIGHT, padx=10, pady=4)

    # === ANIMATIONS & HUD ===

    def _start_boot_sequence(self) -> None:
        """Kick off fake console boot animation."""
        self.output_text.delete("1.0", tk.END)

        self._boot_lines = [
            "[CYBERTEST v1.0.0] initializing diagnostic core...",
            "[OK]   loading neon theme shaders",
            "[OK]   linking pytest runtime module",
            "[OK]   scanning local filesystem for test targets",
            "[OK]   entropy pool charged",
            "[SYS]  console interface online",
            "",
            "[HINT] select a file or folder to begin test run.",
            "",
        ]
        self._boot_step(0)

    def _boot_step(self, index: int) -> None:
        """Print boot lines one by one with delay."""
        if index < len(self._boot_lines):
            line = self._boot_lines[index]
            self.output_text.insert(tk.END, line + "\n")
            self.output_text.see(tk.END)
            self.after(160, self._boot_step, index + 1)
        else:
            self.boot_in_progress = False
            self.select_button.config(state=tk.NORMAL, bg=NEON_PINK)
            self.cursor_label.config(text="> READY _")

    def _animate_scanline(self) -> None:
        """Animate a small scanline bar moving across the top of the output."""
        width = self.scan_canvas.winfo_width()
        height = self.scan_canvas.winfo_height()

        self.scan_canvas.delete("scanline")

        if width > 0 and height > 0:
            x1 = self.scan_x
            x2 = self.scan_x + 80
            if x2 > width:
                x2 = width
            self.scan_canvas.create_rectangle(
                x1,
                0,
                x2,
                height,
                fill="#1b2238",
                outline="",
                tags="scanline",
            )

            self.scan_x += 12
            if self.scan_x > width:
                self.scan_x = -80

        self.after(50, self._animate_scanline)

    def _blink_cursor(self) -> None:
        """Toggle blinking cursor in status label."""
        text = self.cursor_label.cget("text")
        if self.cursor_on:
            if text.endswith("_"):
                text = text[:-1] + " "
        else:
            if not text.endswith("_"):
                text = text.rstrip() + "_"
        self.cursor_on = not self.cursor_on
        self.cursor_label.config(text=text)
        self.after(500, self._blink_cursor)

    def _update_hud(self) -> None:
        """Fake CPU/RAM HUD updates."""
        delta = random.randint(-10, 10)
        base = self.cpu_usage or random.randint(15, 40)
        self.cpu_usage = max(5, min(98, base + delta))

        self.ram_used_gb = round(random.uniform(3.0, 14.0), 1)

        self.cpu_label.config(text=f"CPU: {self.cpu_usage:2d} %")
        self.ram_label.config(
            text=f"RAM: {self.ram_used_gb:4.1f} / {self.ram_total_gb:.0f} GB",
        )

        self._draw_bar(self.cpu_bar, self.cpu_usage / 100.0, NEON_CYAN)
        self._draw_bar(self.ram_bar, self.ram_used_gb / self.ram_total_gb, NEON_PINK)

        self.after(900, self._update_hud)

    @staticmethod
    def _draw_bar(canvas: tk.Canvas, fill_ratio: float, color: str) -> None:
        """Draw a simple filled bar on the given canvas."""
        canvas.delete("bar")
        width = canvas.winfo_width() or 160
        height = canvas.winfo_height() or 10
        fill_width = int(width * max(0.0, min(1.0, fill_ratio)))
        canvas.create_rectangle(
            0,
            0,
            fill_width,
            height,
            fill=color,
            outline="",
            tags="bar",
        )

    # === TEST SUMMARY & HISTORY ===

    def _parse_test_summary(self, text: str) -> None:
        """
        Parse pytest output for summary counts and update HUD labels.

        Looks for patterns like:
        "3 passed, 1 failed, 2 skipped in 0.12s"
        """
        passed = failed = errors = skipped = 0

        pattern_map = {
            "passed": "passed",
            "failed": "failed",
            "error": "errors",
            "errors": "errors",
            "skipped": "skipped",
        }

        for line in text.splitlines():
            if (
                " passed" in line
                or " failed" in line
                or " skipped" in line
                or " error" in line
            ):
                for key, label in pattern_map.items():
                    for match in re.finditer(rf"(\d+)\s+{key}", line):
                        value = int(match.group(1))
                        if label == "passed":
                            passed += value
                        elif label == "failed":
                            failed += value
                        elif label == "errors":
                            errors += value
                        elif label == "skipped":
                            skipped += value

        total = passed + failed + errors + skipped

        self.tests_passed = passed
        self.tests_failed = failed
        self.tests_errors = errors
        self.tests_skipped = skipped
        self.tests_total = total

        self.summary_total.config(text=f"Total: {total}")
        self.summary_passed.config(text=f"Passed: {passed}")
        self.summary_failed.config(text=f"Failed: {failed}")
        self.summary_errors.config(text=f"Errors: {errors}")
        self.summary_skipped.config(text=f"Skipped: {skipped}")

    def _add_run_to_history(self, exit_code: int, flag: str, output: str) -> None:
        """Record this run in the last 5 runs history with full output."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "OK"
        if exit_code != 0 or self.tests_failed > 0 or self.tests_errors > 0:
            status = "ISSUE"

        target_type = "FOLDER" if self.is_directory else "FILE"
        name = self.selected_path or "?"
        name = os.path.basename(name) or name

        summary = (
            f"{timestamp} | {status} | code={exit_code} | "
            f"T:{self.tests_total} P:{self.tests_passed} "
            f"F:{self.tests_failed} E:{self.tests_errors} S:{self.tests_skipped} | "
            f"{target_type}:{name}"
        )

        entry = {
            "summary": summary,
            "output": output,
            "exit_code": exit_code,
            "flag": flag,
            "timestamp": timestamp,
            "target_type": target_type,
            "target_name": name,
            "counts": {
                "total": self.tests_total,
                "passed": self.tests_passed,
                "failed": self.tests_failed,
                "errors": self.tests_errors,
                "skipped": self.tests_skipped,
            },
        }

        self.run_history.append(entry)
        self.run_history = self.run_history[-5:]  # keep last 5

        # Show newest at top
        self.history_listbox.delete(0, tk.END)
        for item in reversed(self.run_history):
            self.history_listbox.insert(tk.END, item["summary"])

    def _on_history_select(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        """When user clicks an item in last 5 runs, show that output in the terminal."""
        selection = self.history_listbox.curselection()
        if not selection:
            return

        display_index = selection[0]
        if not self.run_history:
            return

        # Listbox shows newest at top; run_history has newest at end
        history_index = len(self.run_history) - 1 - display_index
        if history_index < 0 or history_index >= len(self.run_history):
            return

        entry = self.run_history[history_index]
        output = entry.get("output", "")

        if not output:
            return

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, output)
        self.output_text.see(tk.END)
        self.cursor_label.config(text="> HISTORY VIEW _")

    # === CORE LOGIC ===

    def _on_mode_change(self) -> None:
        """Update UI elements when mode changes."""
        mode = self.mode_var.get()
        if mode == "file":
            self.select_button.config(text="SELECT FILE")
        else:
            self.select_button.config(text="SELECT FOLDER")

        self.selected_path = None
        self.is_directory = False
        self.path_label.config(text="// no target selected")
        self.run_button.config(state=tk.DISABLED, bg="#555555")
        self.output_text.delete("1.0", tk.END)

    def select_path(self) -> None:
        """Open file or folder picker based on current mode."""
        mode = self.mode_var.get()

        if mode == "file":
            path = filedialog.askopenfilename(
                title="Select Python file to test",
                filetypes=[("Python files", "*.py"), ("All files", "*.*")],
            )
            is_directory = False
        else:
            path = filedialog.askdirectory(
                title="Select folder for pytest (auto-detects test_*.py)",
            )
            is_directory = True

        if not path:
            return

        self.selected_path = path
        self.is_directory = is_directory

        label_prefix = "// file: " if not is_directory else "// folder: "
        self.path_label.config(text=f"{label_prefix}{path}")
        self.run_button.config(state=tk.NORMAL, bg=NEON_PINK)

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(
            tk.END,
            "[READY] target locked. execute RUN PYTEST to begin.\n\n",
        )
        self.output_text.see(tk.END)

    def run_tests(self) -> None:
        """Run pytest on the selected path and display the output."""
        if not self.selected_path:
            messagebox.showwarning(
                "No target",
                "Select a file or folder first, runner.",
            )
            return

        flag = self.flag_var.get()

        self.output_text.delete("1.0", tk.END)
        target_type = "FOLDER" if self.is_directory else "FILE"
        self.output_text.insert(
            tk.END,
            f"[BOOT] pytest engaged on {target_type}:\n{self.selected_path}\n",
        )
        if flag and flag.lower() != "normal":
            self.output_text.insert(tk.END, f"[FLAG] {flag}\n")
        self.output_text.insert(tk.END, "\n")
        self.output_text.update_idletasks()

        stdout, stderr, return_code = run_pytest(
            self.selected_path,
            self.is_directory,
            flag=flag,
        )

        self.last_stdout = stdout
        self.last_stderr = stderr

        if stdout:
            self.output_text.insert(tk.END, "=== PYTEST OUTPUT ===\n")
            self.output_text.insert(tk.END, stdout + "\n")

        if stderr:
            self.output_text.insert(tk.END, "=== PYTEST ERRORS ===\n")
            self.output_text.insert(tk.END, stderr + "\n")

        combined = (stdout or "") + "\n" + (stderr or "")
        self._parse_test_summary(combined)

        self.output_text.insert(
            tk.END,
            f"\n[EXIT CODE] {return_code}\n",
        )
        self.output_text.see(tk.END)

        # Take snapshot of full terminal output for history
        full_output = self.output_text.get("1.0", tk.END)
        self._add_run_to_history(return_code, flag, full_output)

        if self.tests_failed > 0 or self.tests_errors > 0 or return_code != 0:
            self.cursor_label.config(text="> RUN COMPLETE (ISSUES) _")
        else:
            self.cursor_label.config(text="> RUN COMPLETE (OK) _")

    def _ensure_output_exists(self) -> bool:
        """Check if there is output to save."""
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo(
                "No output",
                "No terminal feed yet. Run pytest first.",
            )
            return False
        return True

    def save_output_txt(self) -> None:
        """Save current output to a TXT file."""
        if not self._ensure_output_exists():
            return

        file_path = filedialog.asksaveasfilename(
            title="Save output as TXT",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        content = self.output_text.get("1.0", tk.END)
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            messagebox.showinfo("Saved", f"Output saved to:\n{file_path}")
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save file:\n{exc}")

    def save_output_html(self) -> None:
        """
        Save current output to a simple HTML file.

        The output is wrapped in <pre> tags so formatting is preserved.
        """
        if not self._ensure_output_exists():
            return

        file_path = filedialog.asksaveasfilename(
            title="Save output as HTML",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html;*.htm"), ("All files", "*.*")],
        )
        if not file_path:
            return

        content = self.output_text.get("1.0", tk.END)
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n<head>\n"
            "<meta charset='utf-8'>\n"
            "<title>pytest output</title>\n"
            "<style>\n"
            "body { background:#050814; color:#f5f5f5; "
            "font-family:Consolas,monospace; }\n"
            "h2 { color:#00f5ff; }\n"
            "pre { background:#0b1020; padding:1rem; border:1px solid #3dffb8; "
            "color:#e0e0ff; white-space:pre-wrap; }\n"
            "</style>\n"
            "</head>\n<body>\n"
            "<h2>CYBERTEST // pytest output</h2>\n"
            "<pre>\n"
            f"{content}\n"
            "</pre>\n"
            "</body>\n</html>\n"
        )

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)
            messagebox.showinfo("Saved", f"HTML output saved to:\n{file_path}")
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save file:\n{exc}")


def main() -> None:
    """Entry point for the GUI app."""
    app = PytestGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
