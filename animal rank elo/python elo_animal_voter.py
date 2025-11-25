"""
Elo Animal Voting App — Tkinter (full features)

Adds:
1) Copy images into a managed project folder when imported
2) Drag-and-drop image import support (requires tkinterdnd2; optional)
3) Dislike button + Neutral (draw) option
4) Built-in viewer with zoom & rotate (canvas)

Dependencies:
- Pillow (pip install pillow)
- tkinterdnd2 (optional, for drag-and-drop): pip install tkinterdnd2

Author: ChatGPT (GPT-5 Thinking mini)
Date: 2025
"""

import os
import sys
import json
import random
import csv
import datetime
import shutil
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

# Try optional drag-and-drop package
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

# -------------------------
# Configuration / Constants
# -------------------------
DEFAULT_ELO = 1000.0
K_FACTOR = 32.0
THUMBNAIL_SIZE = (140, 100)
DISPLAY_SIZE = (420, 320)
DB_FILENAME = "elo_animal_voter_db.json"
PROJECT_FOLDER = "project_images"
MATCH_HISTORY_LIMIT = 5000
ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

os.makedirs(PROJECT_FOLDER, exist_ok=True)


# -------------------------
# Data Classes
# -------------------------
@dataclass
class ImageRecord:
    id: str
    path: str
    name: str
    rating: float = DEFAULT_ELO
    wins: int = 0
    losses: int = 0
    draws: int = 0
    matches: int = 0
    added_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    def to_dict(self):
        return asdict(self)


@dataclass
class MatchRecord:
    timestamp: str
    winner_id: Optional[str]
    loser_id: Optional[str]
    draw: bool
    winner_rating_before: float
    loser_rating_before: float
    winner_rating_after: float
    loser_rating_after: float

    def to_dict(self):
        return asdict(self)


# -------------------------
# Elo Engine (supports draws)
# -------------------------
class EloEngine:
    def __init__(self, k: float = K_FACTOR):
        self.k = float(k)

    @staticmethod
    def expected_score(r_a: float, r_b: float) -> float:
        qa = 10 ** (r_a / 400.0)
        qb = 10 ** (r_b / 400.0)
        if qa + qb == 0:
            return 0.5
        return qa / (qa + qb)

    def update_ratings(self, ra: float, rb: float, result: float) -> Tuple[float, float]:
        """
        result = 1.0 => A wins
        result = 0.0 => B wins
        result = 0.5 => draw
        """
        ea = self.expected_score(ra, rb)
        eb = self.expected_score(rb, ra)
        new_ra = ra + self.k * (result - ea)
        new_rb = rb + self.k * ((1.0 - result) - eb)
        return new_ra, new_rb


# -------------------------
# Image Manager
# -------------------------
class ImageManager:
    def __init__(self):
        self.images: Dict[str, ImageRecord] = {}
        self.history: List[MatchRecord] = []
        self.elo = EloEngine()
        self._thumb_cache: Dict[str, ImageTk.PhotoImage] = {}
        self._display_cache: Dict[str, ImageTk.PhotoImage] = {}

    def add_image_copy(self, original_path: str) -> Optional[ImageRecord]:
        """Copy the image into the managed project folder and add it."""
        if not os.path.exists(original_path):
            return None
        ext = os.path.splitext(original_path)[1].lower()
        if ext not in ALLOWED_EXT:
            return None
        basename = os.path.basename(original_path)
        base, ext = os.path.splitext(basename)
        dest_name = base + ext
        dest_path = os.path.join(PROJECT_FOLDER, dest_name)
        counter = 1
        while os.path.exists(dest_path):
            dest_name = f"{base}_{counter}{ext}"
            dest_path = os.path.join(PROJECT_FOLDER, dest_name)
            counter += 1
        try:
            shutil.copy2(original_path, dest_path)
        except Exception as e:
            print("Copy failed:", e)
            return None
        return self.add_image(dest_path)

    def add_image(self, path: str) -> Optional[ImageRecord]:
        """Add image by path (assumes file is already in project folder or accessible)."""
        if not os.path.exists(path):
            return None
        uid = self._make_id(path)
        if uid in self.images:
            return self.images[uid]
        name = os.path.basename(path)
        rec = ImageRecord(id=uid, path=os.path.abspath(path), name=name)
        self.images[uid] = rec
        return rec

    def _make_id(self, path: str) -> str:
        absp = os.path.abspath(path)
        return str(abs(hash(absp)))

    def remove_image(self, image_id: str):
        if image_id in self.images:
            del self.images[image_id]
            self._thumb_cache.pop(image_id, None)
            self._display_cache.pop(image_id, None)
            self.history = [h for h in self.history if h.winner_id != image_id and h.loser_id != image_id]

    def record_match(self, a_id: str, b_id: str, result: float):
        """
        result relative to A:
        1.0 => A wins
        0.0 => B wins
        0.5 => draw
        """
        if a_id not in self.images or b_id not in self.images:
            raise KeyError("Image id not found")

        a = self.images[a_id]
        b = self.images[b_id]

        before_a = a.rating
        before_b = b.rating

        new_a, new_b = self.elo.update_ratings(before_a, before_b, result)

        # apply stats
        if result == 1.0:
            a.wins += 1
            b.losses += 1
            winner_id, loser_id = a_id, b_id
        elif result == 0.0:
            b.wins += 1
            a.losses += 1
            winner_id, loser_id = b_id, a_id
        else:
            a.draws += 1
            b.draws += 1
            winner_id, loser_id = None, None

        a.matches += 1
        b.matches += 1
        a.rating = new_a
        b.rating = new_b

        rec = MatchRecord(
            timestamp=datetime.datetime.utcnow().isoformat(),
            winner_id=winner_id,
            loser_id=loser_id,
            draw=(result == 0.5),
            winner_rating_before=before_a if winner_id == a_id else before_b if winner_id == b_id else before_a,
            loser_rating_before=before_b if loser_id == b_id else before_a if loser_id == a_id else before_b,
            winner_rating_after=new_a if winner_id == a_id else new_b if winner_id == b_id else new_a,
            loser_rating_after=new_b if loser_id == b_id else new_a if loser_id == a_id else new_b,
        )
        self.history.insert(0, rec)
        if len(self.history) > MATCH_HISTORY_LIMIT:
            self.history = self.history[:MATCH_HISTORY_LIMIT]

    def get_random_pair(self) -> Optional[Tuple[ImageRecord, ImageRecord]]:
        ids = list(self.images.keys())
        if len(ids) < 2:
            return None
        a, b = random.sample(ids, 2)
        return self.images[a], self.images[b]

    def get_smart_pair(self) -> Optional[Tuple[ImageRecord, ImageRecord]]:
        ids = list(self.images.keys())
        if len(ids) < 2:
            return None
        a_id = random.choice(ids)
        a = self.images[a_id]
        candidates = [(abs(a.rating - self.images[i].rating), i) for i in ids if i != a_id]
        candidates.sort(key=lambda x: x[0])
        top_k = min(6, len(candidates))
        chosen = random.choice(candidates[:top_k])
        b_id = chosen[1]
        b = self.images[b_id]
        return a, b

    def ranking(self) -> List[ImageRecord]:
        return sorted(self.images.values(), key=lambda x: x.rating, reverse=True)

    def save_to_file(self, filename: str = DB_FILENAME):
        data = {
            "images": {iid: self.images[iid].to_dict() for iid in self.images},
            "history": [h.to_dict() for h in self.history],
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return filename

    def load_from_file(self, filename: str = DB_FILENAME):
        if not os.path.exists(filename):
            raise FileNotFoundError(filename)
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.images = {}
        for iid, rec in data.get("images", {}).items():
            self.images[iid] = ImageRecord(**rec)
        self.history = [MatchRecord(**h) for h in data.get("history", [])]
        self.clear_caches()

    # image helpers
    def _make_thumbnail(self, path: str, size=THUMBNAIL_SIZE) -> ImageTk.PhotoImage:
        try:
            img = Image.open(path)
            img.thumbnail(size, Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            return tk_img
        except Exception:
            img = Image.new("RGBA", size, (100, 100, 100))
            return ImageTk.PhotoImage(img)

    def get_thumbnail(self, image_id: str) -> ImageTk.PhotoImage:
        if image_id in self._thumb_cache:
            return self._thumb_cache[image_id]
        rec = self.images.get(image_id)
        if not rec:
            img = Image.new("RGBA", THUMBNAIL_SIZE, (120, 120, 120))
            return ImageTk.PhotoImage(img)
        tk_img = self._make_thumbnail(rec.path)
        self._thumb_cache[image_id] = tk_img
        return tk_img

    def _make_display_image(self, path: str, size=DISPLAY_SIZE) -> ImageTk.PhotoImage:
        try:
            img = Image.open(path)
            img.thumbnail(size, Image.LANCZOS)
            bg_w, bg_h = size
            bg = Image.new("RGBA", size, (30, 30, 30))
            img_w, img_h = img.size
            offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
            bg.paste(img, offset)
            return ImageTk.PhotoImage(bg)
        except Exception:
            img = Image.new("RGBA", size, (60, 60, 60))
            return ImageTk.PhotoImage(img)

    def get_display_image(self, image_id: str) -> ImageTk.PhotoImage:
        if image_id in self._display_cache:
            return self._display_cache[image_id]
        rec = self.images.get(image_id)
        if not rec:
            img = Image.new("RGBA", DISPLAY_SIZE, (60, 60, 60))
            return ImageTk.PhotoImage(img)
        tk_img = self._make_display_image(rec.path)
        self._display_cache[image_id] = tk_img
        return tk_img

    def clear_caches(self):
        self._thumb_cache.clear()
        self._display_cache.clear()


# -------------------------
# Image viewer with zoom & rotate
# -------------------------
class ImageViewer(tk.Toplevel):
    def __init__(self, master, image_path: str):
        super().__init__(master)
        self.title(os.path.basename(image_path))
        self.geometry("800x600")
        self.configure(bg="#111111")

        self.orig_image = Image.open(image_path).convert("RGBA")
        self.display_image = self.orig_image.copy()
        self.zoom = 1.0
        self.angle = 0

        # canvas for image
        self.canvas = tk.Canvas(self, bg="#111111")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<MouseWheel>", self._on_wheel)  # Windows
        self.canvas.bind("<Button-4>", self._on_wheel)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_wheel)  # Linux scroll down

        # controls
        ctrl = tk.Frame(self, bg="#222222")
        ctrl.pack(fill="x")
        tk.Button(ctrl, text="Zoom +", command=lambda: self._zoom(1.2)).pack(side="left", padx=6, pady=6)
        tk.Button(ctrl, text="Zoom -", command=lambda: self._zoom(1/1.2)).pack(side="left", padx=6, pady=6)
        tk.Button(ctrl, text="Rotate ⟲", command=lambda: self._rotate(-90)).pack(side="left", padx=6, pady=6)
        tk.Button(ctrl, text="Rotate ⟳", command=lambda: self._rotate(90)).pack(side="left", padx=6, pady=6)
        tk.Button(ctrl, text="Reset", command=self._reset).pack(side="left", padx=6, pady=6)
        tk.Button(ctrl, text="Close", command=self.destroy).pack(side="right", padx=6, pady=6)

        self._render_image()

    def _render_image(self):
        # apply zoom & rotation
        w, h = self.orig_image.size
        img = self.orig_image.rotate(self.angle, expand=True)
        nw, nh = int(img.width * self.zoom), int(img.height * self.zoom)
        img = img.resize((nw, nh), Image.LANCZOS)
        # center within canvas
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, image=self.photo, anchor="center")
        # ensure image persists
        self.canvas.image = self.photo

    def _zoom(self, factor):
        self.zoom *= factor
        # clamp zoom
        if self.zoom < 0.1:
            self.zoom = 0.1
        if self.zoom > 10:
            self.zoom = 10
        self._render_image()

    def _rotate(self, deg):
        self.angle = (self.angle + deg) % 360
        self._render_image()

    def _reset(self):
        self.zoom = 1.0
        self.angle = 0
        self._render_image()

    def _on_wheel(self, event):
        # Normalize across platforms
        delta = 0
        if hasattr(event, "delta"):
            delta = event.delta
        elif getattr(event, "num", None) == 4:
            delta = 120
        elif getattr(event, "num", None) == 5:
            delta = -120
        if delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(1 / 1.1)


# -------------------------
# GUI Application (Tkinter-only)
# -------------------------
class EloVotingApp:
    def __init__(self, root):
        # If available use TkinterDnD root for drag-and-drop support
        if DND_AVAILABLE and isinstance(root, TkinterDnD.Tk):
            self.root = root
        else:
            self.root = root
        self.root.title("🐾 Elo Animal Voting — Tkinter")
        self.root.geometry("1160x760")
        self.im = ImageManager()
        self.current_pair: Optional[Tuple[ImageRecord, ImageRecord]] = None
        self.pair_mode_smart = True
        self._build_ui()

    # -------------------------
    # Build UI
    # -------------------------
    def _build_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add Images (copy to project)", command=self.ui_add_images_copy)
        file_menu.add_command(label="Save Session", command=self.ui_save_session)
        file_menu.add_command(label="Load Session", command=self.ui_load_session)
        file_menu.add_separator()
        file_menu.add_command(label="Export Leaderboard CSV", command=self.ui_export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Show Leaderboard", command=self.ui_show_leaderboard)
        view_menu.add_command(label="Show Stats", command=self.ui_show_stats)
        view_menu.add_command(label="Show Match History", command=self.ui_show_history)
        menubar.add_cascade(label="View", menu=view_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Toggle Pair Selection Mode", command=self.ui_toggle_pair_mode)
        settings_menu.add_command(label="Reset All Ratings", command=self.ui_reset_ratings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.root.config(menu=menubar)

        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Label(main_frame, text="🐾 Pick the CUTER animal!", font=("Helvetica", 20, "bold"))
        header.pack(pady=6)

        # top area: drag-and-drop hint
        dnd_hint = tk.Label(main_frame, text="Drag & drop images here (if supported) or use Add Images. Imported images are copied into ./project_images", fg="#0055aa")
        dnd_hint.pack(pady=2)

        # Voting area
        vote_frame = tk.Frame(main_frame)
        vote_frame.pack(fill="both", expand=True, pady=6)

        # Left panel
        self.left_panel = tk.Frame(vote_frame)
        self.left_panel.pack(side="left", expand=True, padx=8)

        self.left_image_label = tk.Label(self.left_panel, text="Left Image", bd=2, relief="sunken", width=DISPLAY_SIZE[0]//10, height=DISPLAY_SIZE[1]//20)
        self.left_image_label.pack(pady=8)
        self.left_image_label.bind("<Button-1>", lambda e: self._on_left_vote_click())

        # left vote/dislike/neutral
        left_btns = tk.Frame(self.left_panel)
        left_btns.pack()
        tk.Button(left_btns, text="Vote 👍", command=lambda: self._vote_side("left", vote_type="win")).pack(side="left", padx=4)
        tk.Button(left_btns, text="Dislike 👎", command=lambda: self._vote_side("left", vote_type="dislike")).pack(side="left", padx=4)
        tk.Button(left_btns, text="Neutral 🤝", command=lambda: self._vote_side("left", vote_type="neutral")).pack(side="left", padx=4)

        self.left_info_label = tk.Label(self.left_panel, text="", anchor="w", justify="left")
        self.left_info_label.pack(padx=4, pady=4)

        # Middle controls
        control_panel = tk.Frame(vote_frame, width=160)
        control_panel.pack(side="left", padx=6, fill="y")

        self.next_btn = tk.Button(control_panel, text="Next Pair", command=self.ui_next_pair, width=18)
        self.next_btn.pack(pady=4, padx=6)
        self.random_btn = tk.Button(control_panel, text="Random Pair", command=self.ui_random_pair, width=18)
        self.random_btn.pack(pady=4, padx=6)
        self.swap_btn = tk.Button(control_panel, text="Swap Sides", command=self.ui_swap_pair, width=18)
        self.swap_btn.pack(pady=4, padx=6)
        self.reset_cache_btn = tk.Button(control_panel, text="Clear Image Cache", command=self._clear_image_cache, width=18)
        self.reset_cache_btn.pack(pady=6, padx=6)
        self.mode_label = tk.Label(control_panel, text="Mode: Smart Pairing")
        self.mode_label.pack(pady=8)
        tk.Button(control_panel, text="Open Gallery", command=self.ui_open_gallery, width=18).pack(pady=4)
        tk.Button(control_panel, text="Open Project Folder", command=lambda: self._open_folder(PROJECT_FOLDER), width=18).pack(pady=4)

        # Right panel
        self.right_panel = tk.Frame(vote_frame)
        self.right_panel.pack(side="left", expand=True, padx=8)

        self.right_image_label = tk.Label(self.right_panel, text="Right Image", bd=2, relief="sunken", width=DISPLAY_SIZE[0]//10, height=DISPLAY_SIZE[1]//20)
        self.right_image_label.pack(pady=8)
        self.right_image_label.bind("<Button-1>", lambda e: self._on_right_vote_click())

        right_btns = tk.Frame(self.right_panel)
        right_btns.pack()
        tk.Button(right_btns, text="Vote 👍", command=lambda: self._vote_side("right", vote_type="win")).pack(side="left", padx=4)
        tk.Button(right_btns, text="Dislike 👎", command=lambda: self._vote_side("right", vote_type="dislike")).pack(side="left", padx=4)
        tk.Button(right_btns, text="Neutral 🤝", command=lambda: self._vote_side("right", vote_type="neutral")).pack(side="left", padx=4)

        self.right_info_label = tk.Label(self.right_panel, text="", anchor="w", justify="left")
        self.right_info_label.pack(padx=4, pady=4)

        # Bottom controls
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(side="bottom", fill="x", pady=8)

        tk.Button(bottom_frame, text="Add Images (copy)", command=self.ui_add_images_copy).pack(side="left", padx=6)
        tk.Button(bottom_frame, text="Leaderboard", command=self.ui_show_leaderboard).pack(side="left", padx=6)
        tk.Button(bottom_frame, text="History", command=self.ui_show_history).pack(side="left", padx=6)
        tk.Button(bottom_frame, text="Stats", command=self.ui_show_stats).pack(side="left", padx=6)
        tk.Button(bottom_frame, text="Export CSV", command=self.ui_export_csv).pack(side="left", padx=6)

        # status
        self.status_label = tk.Label(main_frame, text="No images loaded. Add or drag images to begin.", anchor="w")
        self.status_label.pack(fill="x", padx=6, pady=6)

        # Drag-and-drop binding (if available)
        if DND_AVAILABLE:
            try:
                if hasattr(self.root, "drop_target_register"):
                    drop_target = self.root
                else:
                    drop_target = None
                if drop_target:
                    drop_target.drop_target_register(DND_FILES)
                    drop_target.dnd_bind('<<Drop>>', self._on_dnd)
            except Exception:
                pass

        self._update_mode_label()
        self.ui_next_pair(initial=True)

    # -------------------------
    # Utilities
    # -------------------------
    def _open_folder(self, folder_path):
        try:
            if sys.platform == "win32":
                os.startfile(os.path.abspath(folder_path))
            elif sys.platform == "darwin":
                os.system(f'open "{os.path.abspath(folder_path)}"')
            else:
                os.system(f'xdg-open "{os.path.abspath(folder_path)}"')
        except Exception as e:
            messagebox.showinfo("Open folder", f"Could not open folder: {e}")

    # -------------------------
    # Drag & Drop handler
    # -------------------------
    def _on_dnd(self, event):
        """
        event.data is a string of filenames separated by spaces; filenames with spaces are enclosed in {}
        Format example: {C:\path with spaces\img 1.jpg} C:\another\img2.png
        """
        data = event.data
        # parse into file paths
        files = []
        cur = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                cur = ""
            elif ch == "}":
                in_brace = False
                files.append(cur)
                cur = ""
            elif ch == " " and not in_brace:
                if cur:
                    files.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur:
            files.append(cur)
        # filter and copy into project folder
        added = 0
        for f in files:
            if os.path.isfile(f) and os.path.splitext(f)[1].lower() in ALLOWED_EXT:
                rec = self.im.add_image_copy(f)
                if rec:
                    added += 1
        self.im.clear_caches()
        self.status_label.config(text=f"Drag & drop: added {added} images. Total: {len(self.im.images)}")
        self.ui_next_pair()

    # -------------------------
    # Add images (copy into project folder)
    # -------------------------
    def ui_add_images_copy(self):
        files = filedialog.askopenfilenames(title="Select image files to copy into project", filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp"), ("All files", "*.*")])
        added = 0
        for f in files:
            rec = self.im.add_image_copy(f)
            if rec:
                added += 1
        self.im.clear_caches()
        self.status_label.config(text=f"Added {added} images (copied). Total: {len(self.im.images)}")
        self.ui_next_pair()

    # -------------------------
    # Save / Load / Export
    # -------------------------
    def ui_save_session(self):
        path = filedialog.asksaveasfilename(title="Save session as JSON", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            self.im.save_to_file(path)
            messagebox.showinfo("Saved", f"Session saved to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def ui_load_session(self):
        path = filedialog.askopenfilename(title="Open session JSON", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            self.im.load_from_file(path)
            self.im.clear_caches()
            self.status_label.config(text=f"Loaded session: {len(self.im.images)} images")
            self.ui_next_pair()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load: {e}")

    def ui_export_csv(self):
        path = filedialog.asksaveasfilename(title="Export leaderboard CSV", defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["rank", "id", "name", "rating", "wins", "losses", "draws", "matches", "path"])
                for i, rec in enumerate(self.im.ranking(), start=1):
                    writer.writerow([i, rec.id, rec.name, f"{rec.rating:.2f}", rec.wins, rec.losses, rec.draws, rec.matches, rec.path])
            messagebox.showinfo("Exported", f"Leaderboard exported to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    # -------------------------
    # Pair mode / Reset
    # -------------------------
    def ui_toggle_pair_mode(self):
        self.pair_mode_smart = not self.pair_mode_smart
        self._update_mode_label()
        self.ui_next_pair()

    def _update_mode_label(self):
        mode_text = "Smart Pairing" if self.pair_mode_smart else "Random Pairing"
        self.mode_label.config(text=f"Mode: {mode_text}")

    def ui_reset_ratings(self):
        if not self.im.images:
            return
        if not messagebox.askyesno("Confirm Reset", "Reset all ratings and stats? This cannot be undone."):
            return
        for rec in self.im.images.values():
            rec.rating = DEFAULT_ELO
            rec.wins = rec.losses = rec.draws = rec.matches = 0
        self.im.history.clear()
        self.im.clear_caches()
        self.status_label.config(text="All ratings reset.")
        self.ui_next_pair()

    def _clear_image_cache(self):
        self.im.clear_caches()
        messagebox.showinfo("Cache cleared", "Image caches cleared. Thumbnails will be regenerated.")

    # -------------------------
    # Pair selection & display
    # -------------------------
    def ui_next_pair(self, initial=False):
        if len(self.im.images) < 2:
            self.current_pair = None
            self._update_display(None, None)
            if not initial:
                messagebox.showinfo("Need images", "Please add at least two images to start voting.")
            return
        pair = self.im.get_smart_pair() if self.pair_mode_smart else self.im.get_random_pair()
        if not pair:
            self.current_pair = None
            self._update_display(None, None)
            return
        # randomize sides sometimes
        if random.random() < 0.5:
            a, b = pair
        else:
            b, a = pair
        self.current_pair = (a, b)
        self._update_display(a, b)

    def ui_random_pair(self):
        self.pair_mode_smart = False
        self._update_mode_label()
        self.ui_next_pair()

    def ui_swap_pair(self):
        if self.current_pair:
            a, b = self.current_pair
            self.current_pair = (b, a)
            self._update_display(b, a)

    def _update_display(self, left: Optional[ImageRecord], right: Optional[ImageRecord]):
        # left
        if left:
            left_img = self.im.get_display_image(left.id)
            self.left_image_label.config(image=left_img)
            self.left_image_label.image = left_img
            self.left_info_label.config(text=self._format_info_text(left))
        else:
            blank = self._make_placeholder(DISPLAY_SIZE)
            self.left_image_label.config(image=blank)
            self.left_image_label.image = blank
            self.left_info_label.config(text="")

        # right
        if right:
            right_img = self.im.get_display_image(right.id)
            self.right_image_label.config(image=right_img)
            self.right_image_label.image = right_img
            self.right_info_label.config(text=self._format_info_text(right))
        else:
            blank = self._make_placeholder(DISPLAY_SIZE)
            self.right_image_label.config(image=blank)
            self.right_image_label.image = blank
            self.right_info_label.config(text="")

    def _make_placeholder(self, size):
        img = Image.new("RGBA", size, (40, 40, 40))
        tkimg = ImageTk.PhotoImage(img)
        return tkimg

    def _format_info_text(self, rec: ImageRecord):
        return f"{rec.name}\nRating: {rec.rating:.1f}\nW:{rec.wins} L:{rec.losses} D:{rec.draws} M:{rec.matches}"

    # -------------------------
    # Voting helpers (vote_type: win/dislike/neutral)
    # -------------------------
    def _vote_side(self, side: str, vote_type: str):
        if not self.current_pair:
            return
        left, right = self.current_pair
        if side == "left":
            a, b = left, right
        else:
            a, b = right, left

        if vote_type == "win":
            # A wins
            self.im.record_match(a.id, b.id, result=1.0)
            self.status_label.config(text=f"Recorded: {a.name} beat {b.name} — new ratings: {a.rating:.1f}, {b.rating:.1f}")
        elif vote_type == "dislike":
            # A disliked => B wins (record as B win)
            self.im.record_match(b.id, a.id, result=1.0)
            self.status_label.config(text=f"Recorded: {b.name} beat {a.name} (dislike) — new ratings: {b.rating:.1f}, {a.rating:.1f}")
        elif vote_type == "neutral":
            # draw
            self.im.record_match(a.id, b.id, result=0.5)
            self.status_label.config(text=f"Recorded draw between {a.name} and {b.name} — new ratings: {a.rating:.1f}, {b.rating:.1f}")
        else:
            return

        # clear caches for both
        self.im._display_cache.pop(left.id, None)
        self.im._display_cache.pop(right.id, None)
        # show simple flash
        self._flash_winner_after_vote(side, vote_type)
        self.ui_next_pair()

    def _on_left_vote_click(self):
        # quick left click counts as a normal win
        self._vote_side("left", "win")

    def _on_right_vote_click(self):
        self._vote_side("right", "win")

    def _flash_winner_after_vote(self, voted_side: str, vote_type: str):
        try:
            if voted_side == "left":
                lbl = self.left_image_label
            else:
                lbl = self.right_image_label
            # show border briefly (color differs for neutral/dislike)
            if vote_type == "neutral":
                color = "lightblue"
            elif vote_type == "dislike":
                color = "red"
            else:
                color = "gold"
            orig_bd = lbl.cget("bd")
            lbl.config(bd=6, relief="solid", highlightbackground=color)
            lbl.after(220, lambda: lbl.config(bd=2, relief="sunken"))
        except Exception:
            pass

    # -------------------------
    # Leaderboard / Stats / History
    # -------------------------
    def ui_show_leaderboard(self):
        win = tk.Toplevel(self.root)
        win.title("Leaderboard")
        win.geometry("800x540")

        hdr = tk.Label(win, text="🏆 Leaderboard — Ranking by Elo Rating", font=("Helvetica", 14, "bold"))
        hdr.pack(pady=8)

        columns = ("rank", "name", "rating", "wins", "losses", "draws", "matches")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=18)
        for col in columns:
            tree.heading(col, text=col.title())
            tree.column(col, width=100, anchor="center")
        tree.column("name", width=320, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for i, rec in enumerate(self.im.ranking(), start=1):
            tree.insert("", "end", values=(i, rec.name, f"{rec.rating:.2f}", rec.wins, rec.losses, rec.draws, rec.matches), tags=(rec.id,))

        # right-click menu
        menu = tk.Menu(win, tearoff=0)
        menu.add_command(label="Open in Viewer", command=lambda: self._open_selected_image_file(tree))
        menu.add_command(label="Remove from library", command=lambda: self._remove_selected_image(tree))

        def popup(event):
            iid = tree.identify_row(event.y)
            if iid:
                tree.selection_set(iid)
                menu.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", popup)

    def _open_selected_image_file(self, tree):
        selected = tree.selection()
        if not selected:
            return
        iid = selected[0]
        tags = tree.item(iid, "tags")
        if tags:
            img_id = tags[0]
            rec = self.im.images.get(img_id)
            if rec:
                ImageViewer(self.root, rec.path)

    def _remove_selected_image(self, tree):
        selected = tree.selection()
        if not selected:
            return
        iid = selected[0]
        tags = tree.item(iid, "tags")
        if not tags:
            return
        img_id = tags[0]
        if not messagebox.askyesno("Confirm remove", "Remove selected image from library? This will also remove it from history. File will remain in project folder."):
            return
        self.im.remove_image(img_id)
        self.status_label.config(text=f"Removed image. Total now: {len(self.im.images)}")
        self.ui_next_pair()

    def ui_show_stats(self):
        win = tk.Toplevel(self.root)
        win.title("Statistics")
        win.geometry("520x420")

        hdr = tk.Label(win, text="📊 Statistics", font=("Helvetica", 14, "bold"))
        hdr.pack(pady=8)

        total_images = len(self.im.images)
        avg_rating = (sum(r.rating for r in self.im.images.values()) / total_images) if total_images else 0.0
        top = self.im.ranking()[:7]

        stats_txt = f"Total images: {total_images}\nTotal matches recorded: {len(self.im.history)}\nAverage rating: {avg_rating:.1f}\n"
        stats_txt += "Top 7:\n"
        for i, r in enumerate(top, 1):
            stats_txt += f" {i}. {r.name} — {r.rating:.1f} (W:{r.wins} L:{r.losses} D:{r.draws})\n"

        txt = tk.Text(win, wrap="word", height=18)
        txt.insert("1.0", stats_txt)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=8, pady=8)

    def ui_show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Match History")
        win.geometry("920x520")

        hdr = tk.Label(win, text="🕒 Match History (most recent first)", font=("Helvetica", 14, "bold"))
        hdr.pack(pady=8)

        columns = ("time", "winner", "loser", "draw", "winner_before", "loser_before", "winner_after", "loser_after")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=20)
        for col in columns:
            tree.heading(col, text=col.title())
            tree.column(col, width=110, anchor="center")
        tree.column("winner", width=240)
        tree.column("loser", width=240)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for rec in self.im.history:
            wname = self.im.images.get(rec.winner_id).name if rec.winner_id in self.im.images and rec.winner_id else ("-" if rec.draw else "-")
            lname = self.im.images.get(rec.loser_id).name if rec.loser_id in self.im.images and rec.loser_id else ("-" if rec.draw else "-")
            tree.insert("", "end", values=(rec.timestamp, wname, lname, str(rec.draw), f"{rec.winner_rating_before:.1f}", f"{rec.loser_rating_before:.1f}", f"{rec.winner_rating_after:.1f}", f"{rec.loser_rating_after:.1f}"))

    # -------------------------
    # Gallery
    # -------------------------
    def ui_open_gallery(self):
        win = tk.Toplevel(self.root)
        win.title("Gallery")
        win.geometry("980x640")
        win.config(bg="#222222")

        hdr = tk.Label(win, text="🖼️ Gallery — Click thumbnail to view details", font=("Helvetica", 14, "bold"), bg="#222222", fg="white")
        hdr.pack(pady=8)

        canvas = tk.Canvas(win, bg="#222222")
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#222222")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        cols = 6
        i = 0
        for rec in self.im.ranking():
            row = i // cols
            col = i % cols
            frame = tk.Frame(scroll_frame, bd=1, relief="solid", bg="#333333")
            frame.grid(row=row, column=col, padx=6, pady=6)
            thumb = self.im.get_thumbnail(rec.id)
            lbl = tk.Label(frame, image=thumb, bg="#333333")
            lbl.image = thumb
            lbl.pack()
            info = tk.Label(frame, text=f"{rec.name}\n{rec.rating:.1f}", justify="center", bg="#333333", fg="white")
            info.pack()
            lbl.bind("<Button-1>", lambda e, rid=rec.id: ImageViewer(self.root, self.im.images[rid].path))
            info.bind("<Button-1>", lambda e, rid=rec.id: ImageViewer(self.root, self.im.images[rid].path))
            i += 1

    def _open_detail_view(self, rec_id: str):
        rec = self.im.images.get(rec_id)
        if not rec:
            return
        ImageViewer(self.root, rec.path)

# -------------------------
# Entry point
# -------------------------
def main():
    if DND_AVAILABLE:
        # create a TkinterDnD root if available to enable native drag & drop
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = EloVotingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
