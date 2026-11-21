"""Always-on-top Tk overlay showing recommendations, with a command box."""
from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

try:
    import tkinter as tk
    from tkinter import scrolledtext
    HAS_TK = True
except Exception:   # pragma: no cover - depends on the host Python build
    HAS_TK = False


class Overlay:
    """Runs a Tk window on the main thread; the advisor loop runs in a worker.

    ``producer`` is called repeatedly in the worker thread and must return the
    text to display (or None to keep the previous text). ``on_command`` gets
    each line typed into the input box and returns a reply string.
    """

    def __init__(self, producer: Callable[[], Optional[str]], on_command: Callable[[str], str],
                 title: str = "CR Stockfish", alpha: float = 0.88, width: int = 460, height: int = 420):
        if not HAS_TK:
            raise RuntimeError("tkinter is not available in this Python; run with --no-overlay")
        self.producer = producer
        self.on_command = on_command
        self._q: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self.root = tk.Tk()
        self.root.title(title)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.root.geometry(f"{width}x{height}+20+20")
        self.root.configure(bg="#111")
        self.text = scrolledtext.ScrolledText(self.root, bg="#111", fg="#e8e8e8", font=("Consolas", 10), wrap="word", borderwidth=0)
        self.text.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        self.text.tag_configure("best", foreground="#7CFC00")
        frame = tk.Frame(self.root, bg="#111")
        frame.pack(fill="x", padx=6, pady=(0, 6))
        self.entry = tk.Entry(frame, bg="#222", fg="#fff", insertbackground="#fff", font=("Consolas", 10))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._submit)
        self.reply = tk.Label(self.root, text="o <card> = opponent played | u undo | r reset | ? help", bg="#111", fg="#999", anchor="w", font=("Consolas", 9))
        self.reply.pack(fill="x", padx=6, pady=(0, 4))
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

    def _submit(self, _evt=None) -> None:
        line = self.entry.get()
        self.entry.delete(0, "end")
        try:
            msg = self.on_command(line)
        except Exception as exc:   # never let a typo kill the overlay
            msg = f"error: {exc}"
        self.reply.configure(text=(msg or "").splitlines()[0][:90] if msg else "")

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                txt = self.producer()
            except Exception as exc:
                txt = f"advisor error: {exc}"
            if txt is not None:
                self._q.put(txt)

    def _pump(self) -> None:
        txt = None
        try:
            while True:
                txt = self._q.get_nowait()
        except queue.Empty:
            pass
        if txt is not None:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("end", txt)
            # highlight the first recommendation line
            idx = self.text.search("1. ", "1.0", stopindex="end")
            if idx:
                self.text.tag_add("best", idx, f"{idx} lineend")
            self.text.configure(state="disabled")
        if not self._stop.is_set():
            self.root.after(150, self._pump)

    def run(self) -> None:
        threading.Thread(target=self._worker, daemon=True).start()
        self.root.after(100, self._pump)
        try:
            self.root.mainloop()
        finally:
            self._stop.set()

    def stop(self) -> None:
        self._stop.set()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
