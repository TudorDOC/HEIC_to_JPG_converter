import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from pathlib import Path

try:
    from pillow_heif import register_heif_opener
    from PIL import Image
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False


# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#0f0f0f"
SURFACE   = "#1a1a1a"
SURFACE2  = "#242424"
ACCENT    = "#f5a623"
ACCENT2   = "#e8913a"
TEXT      = "#f0ede8"
MUTED     = "#888580"
SUCCESS   = "#4caf7d"
ERROR     = "#e05c5c"
BORDER    = "#2e2e2e"

# ── Main App ──────────────────────────────────────────────────────────────────
class HeicConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HEIC → JPG")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.geometry("620x680")

        self.files: list[str] = []
        self.output_dir: str = ""
        self.quality_var = tk.IntVar(value=90)
        self.running = False

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=24)

        # ── Header ────
        header = tk.Frame(self.root, bg=ACCENT, height=3)
        header.pack(fill="x")

        title_frame = tk.Frame(self.root, bg=BG, pady=28)
        title_frame.pack(fill="x", **pad)

        tk.Label(title_frame, text="HEIC  →  JPG", font=("Georgia", 26, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(title_frame, text="Batch convert Apple photos with one click",
                 font=("Georgia", 11, "italic"), bg=BG, fg=MUTED).pack(anchor="w")

        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x", **pad)

        # ── File selector ────
        file_frame = tk.Frame(self.root, bg=BG, pady=20)
        file_frame.pack(fill="x", **pad)

        row = tk.Frame(file_frame, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="SOURCE FILES", font=("Courier", 9, "bold"),
                 bg=BG, fg=MUTED).pack(side="left")

        self.file_count_lbl = tk.Label(row, text="", font=("Courier", 9),
                                       bg=BG, fg=ACCENT)
        self.file_count_lbl.pack(side="right")

        # Drop zone / file list
        list_frame = tk.Frame(self.root, bg=SURFACE, bd=0,
                              highlightbackground=BORDER,
                              highlightthickness=1)
        list_frame.pack(fill="x", **pad)

        self.file_listbox = tk.Listbox(
            list_frame, bg=SURFACE, fg=TEXT, selectbackground=SURFACE2,
            activestyle="none", font=("Courier", 10), height=7, bd=0,
            highlightthickness=0, selectforeground=ACCENT,
            relief="flat"
        )
        scrollbar = tk.Scrollbar(list_frame, orient="vertical",
                                 command=self.file_listbox.yview,
                                 bg=SURFACE2, troughcolor=SURFACE,
                                 activebackground=ACCENT)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side="left", fill="both", expand=True, padx=0)
        scrollbar.pack(side="right", fill="y")

        # Placeholder label
        self.placeholder = tk.Label(
            list_frame, text="No files selected yet.\nClick 'Add Files' to get started.",
            font=("Georgia", 10, "italic"), bg=SURFACE, fg=MUTED
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

        btn_row = tk.Frame(self.root, bg=BG, pady=10)
        btn_row.pack(fill="x", **pad)
        self._btn(btn_row, "＋  Add Files", self._add_files, ACCENT, BG).pack(side="left")
        self._btn(btn_row, "✕  Clear All", self._clear_files, SURFACE2, MUTED,
                  hover=BORDER).pack(side="left", padx=(8, 0))

        sep2 = tk.Frame(self.root, bg=BORDER, height=1)
        sep2.pack(fill="x", **pad)

        # ── Output dir ────
        out_frame = tk.Frame(self.root, bg=BG, pady=18)
        out_frame.pack(fill="x", **pad)

        tk.Label(out_frame, text="OUTPUT FOLDER", font=("Courier", 9, "bold"),
                 bg=BG, fg=MUTED).pack(anchor="w")

        dir_row = tk.Frame(out_frame, bg=SURFACE, highlightbackground=BORDER,
                           highlightthickness=1)
        dir_row.pack(fill="x", pady=(6, 0))

        self.dir_lbl = tk.Label(dir_row, text="  Same folder as source files  (default)",
                                font=("Courier", 10), bg=SURFACE, fg=MUTED,
                                anchor="w")
        self.dir_lbl.pack(side="left", fill="x", expand=True, ipady=9)
        self._btn(dir_row, "Browse", self._pick_output, SURFACE2, TEXT,
                  hover=BORDER, padx=12, pady=8).pack(side="right")

        sep3 = tk.Frame(self.root, bg=BORDER, height=1)
        sep3.pack(fill="x", **pad)

        # ── Quality slider ────
        q_frame = tk.Frame(self.root, bg=BG, pady=18)
        q_frame.pack(fill="x", **pad)

        q_top = tk.Frame(q_frame, bg=BG)
        q_top.pack(fill="x")
        tk.Label(q_top, text="JPEG QUALITY", font=("Courier", 9, "bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        self.q_label = tk.Label(q_top, text="90", font=("Courier", 13, "bold"),
                                bg=BG, fg=ACCENT)
        self.q_label.pack(side="right")

        self.slider = tk.Scale(
            q_frame, from_=30, to=100, orient="horizontal",
            variable=self.quality_var, command=self._update_q,
            bg=BG, fg=TEXT, highlightthickness=0, bd=0,
            troughcolor=SURFACE2, activebackground=ACCENT,
            sliderrelief="flat", length=560, sliderlength=16
        )
        self.slider.pack(fill="x")

        sep4 = tk.Frame(self.root, bg=BORDER, height=1)
        sep4.pack(fill="x", **pad)

        # ── Progress ────
        prog_frame = tk.Frame(self.root, bg=BG, pady=12)
        prog_frame.pack(fill="x", **pad)

        self.progress_lbl = tk.Label(prog_frame, text="Ready.",
                                     font=("Courier", 10), bg=BG, fg=MUTED)
        self.progress_lbl.pack(anchor="w")

        self.progress_bar_bg = tk.Frame(prog_frame, bg=SURFACE2, height=4)
        self.progress_bar_bg.pack(fill="x", pady=(6, 0))

        self.progress_bar = tk.Frame(self.progress_bar_bg, bg=ACCENT, height=4, width=0)
        self.progress_bar.place(x=0, y=0, height=4)

        # ── Convert button ────
        convert_wrap = tk.Frame(self.root, bg=BG, pady=18)
        convert_wrap.pack(fill="x", **pad)

        self.convert_btn = tk.Button(
            convert_wrap, text="CONVERT",
            font=("Georgia", 14, "bold"),
            bg=ACCENT, fg=BG, activebackground=ACCENT2, activeforeground=BG,
            relief="flat", cursor="hand2", bd=0,
            command=self._start_conversion,
            pady=14
        )
        self.convert_btn.pack(fill="x")

    # ── Helper: styled button ──────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg, fg,
             hover=None, padx=14, pady=7):
        btn = tk.Button(parent, text=text, font=("Courier", 10),
                        bg=bg, fg=fg, activebackground=hover or bg,
                        activeforeground=fg, relief="flat", cursor="hand2",
                        bd=0, command=cmd, padx=padx, pady=pady)
        if hover:
            btn.bind("<Enter>", lambda e: btn.config(bg=hover))
            btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    # ── Actions ───────────────────────────────────────────────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select HEIC files",
            filetypes=[("HEIC files", "*.heic *.HEIC *.heif *.HEIF"), ("All files", "*.*")]
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.file_listbox.insert("end", f"  {Path(p).name}")
        self._update_file_count()

    def _clear_files(self):
        self.files.clear()
        self.file_listbox.delete(0, "end")
        self._update_file_count()
        self._set_progress("Ready.", 0)

    def _pick_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.output_dir = d
            short = d if len(d) <= 48 else "…" + d[-46:]
            self.dir_lbl.config(text=f"  {short}", fg=TEXT)

    def _update_q(self, val):
        self.q_label.config(text=str(int(float(val))))

    def _update_file_count(self):
        n = len(self.files)
        self.file_count_lbl.config(text=f"{n} file{'s' if n != 1 else ''}" if n else "")
        if n:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _set_progress(self, msg, fraction, color=ACCENT):
        self.progress_lbl.config(text=msg)
        total_width = self.progress_bar_bg.winfo_width() or 572
        bar_width = int(total_width * fraction)
        self.progress_bar.config(bg=color, width=bar_width)
        self.progress_bar.place(x=0, y=0, height=4, width=bar_width)

    # ── Conversion logic ──────────────────────────────────────────────────────
    def _start_conversion(self):
        if self.running:
            return
        if not HEIF_AVAILABLE:
            messagebox.showerror("Missing dependency",
                                 "pillow-heif is not installed.\n"
                                 "Run: pip install pillow-heif")
            return
        if not self.files:
            messagebox.showwarning("No files", "Please add at least one HEIC file.")
            return
        self.running = True
        self.convert_btn.config(state="disabled", text="Converting…")
        t = threading.Thread(target=self._convert_all, daemon=True)
        t.start()

    def _convert_all(self):
        total = len(self.files)
        quality = self.quality_var.get()
        ok = fail = 0

        for i, src in enumerate(self.files, 1):
            name = Path(src).stem + ".jpg"
            dest_dir = self.output_dir or str(Path(src).parent)
            dest = os.path.join(dest_dir, name)

            self.root.after(0, self._set_progress,
                            f"Converting {i}/{total}  →  {Path(src).name}",
                            (i - 1) / total)
            try:
                img = Image.open(src)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(dest, "JPEG", quality=quality)
                ok += 1
            except Exception as exc:
                fail += 1
                print(f"[ERROR] {src}: {exc}")

        self.root.after(0, self._done, ok, fail)

    def _done(self, ok, fail):
        self.running = False
        self.convert_btn.config(state="normal", text="CONVERT")
        total = ok + fail
        if fail == 0:
            self._set_progress(
                f"✓  {ok}/{total} converted successfully.", 1.0, SUCCESS)
            messagebox.showinfo("Done", f"All {ok} file(s) converted successfully!")
        else:
            self._set_progress(
                f"⚠  {ok} succeeded, {fail} failed.", ok / total, ERROR)
            messagebox.showwarning("Partial success",
                                   f"{ok} file(s) converted.\n{fail} file(s) failed.")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = HeicConverterApp(root)
    root.mainloop()