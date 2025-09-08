import tkinter as tk
from tkinter import ttk
import time
import threading
from typing import Callable, Optional
import os
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


class DarkRideDashboard(tk.Tk):
    """Batman-themed dashboard window for The Dark Ride.

    This class owns the Tk root to simplify running as a standalone app.
    Use `start()` to begin the periodic UI updates.
    """

    def __init__(self, get_speed: Callable[[], float], get_altitude: Callable[[], float], get_temperature: Callable[[], float], get_accel: Callable[[], tuple[float, float, float]], get_sensor_status: Callable[[], dict], get_data_source: Callable[[], str], get_statistics: Callable[[], dict], reset_statistics: Callable[[], None], *, fullscreen: bool = True, title: str = "The Dark Ride: Bat-Dashboard"):
        super().__init__()
        self.get_speed = get_speed
        self.get_altitude = get_altitude
        self.get_temperature = get_temperature
        self.get_accel = get_accel
        self.get_sensor_status = get_sensor_status
        self.get_data_source = get_data_source
        self.get_statistics = get_statistics
        self.reset_statistics = reset_statistics

        # Basic window setup
        self.title(title)
        self.configure(bg="#000000")  
        self._fullscreen = bool(fullscreen)
        if self._fullscreen:
            self.attributes("-fullscreen", True)
        else:
            self.geometry("800x480")
            self.update_idletasks()
            w = self.winfo_width()
            h = self.winfo_height()
            self.minsize(w, h)
            self.maxsize(w, h)
            self.resizable(False, False)

        # Styling
        self.primary_color = "#FFC400"  # bat yellow
        self.secondary_color = "#FFC400"
        self.text_color = "#FFC400"
        self.card_bg = "#000000"

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", foreground=self.text_color, background=self.card_bg)
        style.configure("Metric.TLabel", font=("Helvetica", 38, "bold"), foreground=self.primary_color, background=self.card_bg)
        style.configure("Unit.TLabel", font=("Helvetica", 16), foreground=self.secondary_color, background=self.card_bg)
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), foreground=self.text_color, background=self.card_bg)
        style.configure("Header.TLabel", font=("Helvetica", 26, "bold"), foreground=self.primary_color, background=self["bg"]) 
        style.configure("HeaderBig.TLabel", font=("Helvetica", 36, "bold"), foreground=self.primary_color, background=self["bg"]) 
        style.configure("ClockBig.TLabel", font=("Helvetica", 36, "bold"), foreground=self.primary_color, background=self["bg"]) 
        style.configure("TFrame", background=self.card_bg)

        # Attempt to load custom bat logo PNG
        self._logo_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "bat_logo.png"))
        self._logo_image_base = None
        if Image is not None and os.path.exists(self._logo_path):
            try:
                self._logo_image_base = Image.open(self._logo_path).convert("RGBA")
            except Exception:
                self._logo_image_base = None

        # Content root stacked over canvas
        self._content_root = tk.Frame(self, bg=self["bg"])
        self._content_root.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Pages container
        self._pages = {}
        self._current_page_idx = 0

        # Layout containers for page 0 (grid)
        page_grid = tk.Frame(self._content_root, bg=self["bg"])
        self._pages[0] = page_grid
        self.header = tk.Frame(page_grid, bg=self["bg"])
        self.header.pack(fill=tk.X, padx=16, pady=(12, 6))

        self.grid_frame = tk.Frame(page_grid, bg=self["bg"])
        self.grid_frame.pack(expand=True, fill=tk.BOTH, padx=16, pady=6)

        # Header
        self._build_header()

        # Metric cards grid (2x2 preferred for 5" layout)
        self.metric_cards = {}
        self._build_metric_card(row=0, col=0, key="speed", title="Speed", unit="mph")
        self._build_metric_card(row=0, col=1, key="altitude", title="Altitude", unit="m")
        self._build_metric_card(row=1, col=0, key="temperature", title="Temperature", unit="°C")
        self._build_metric_card(row=1, col=1, key="accel", title="Acceleration", unit="g XYZ")

        # Footer / controls
        self.footer = tk.Frame(page_grid, bg=self["bg"])
        self.footer.pack(fill=tk.X, padx=16, pady=(6, 12))
        self._build_footer()

        # Build dedicated pages for each metric (pages 1..5)
        self._detail_pages = [
            ("Speed", "speed", "mph"),
            ("Altitude", "altitude", "m"),
            ("Temperature", "temperature", "°C"),
            ("Acceleration", "accel", "g XYZ"),
            ("Statistics", "stats", ""),
        ]
        for i, (title, key, unit) in enumerate(self._detail_pages, start=1):
            frame = tk.Frame(self._content_root, bg=self["bg"])
            self._pages[i] = frame
            if key == "stats":
                self._build_statistics_page(frame)
            else:
                self._build_detail_page(frame, title, key, unit)

        # Show initial page and bind click-to-cycle
        self._show_page(0)
        self._content_root.bind("<Button-1>", self._cycle_page)
        self.bind("<Button-1>", self._cycle_page)  # Also bind to main window

        # Update loop control
        self._stop_event = threading.Event()
        self._update_interval_ms = 200  # 5 Hz

        # Key bindings for development convenience
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Right>", lambda e: self._cycle_page())

    def _toggle_fullscreen(self, _event=None):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _build_header(self):
        # Title left (big) and clock right (big) in one row
        row = tk.Frame(self.header, bg=self["bg"]) 
        row.pack(fill=tk.X)
        left = tk.Frame(row, bg=self["bg"]) 
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        right = tk.Frame(row, bg=self["bg"]) 
        right.pack(side=tk.RIGHT)

        title_label = ttk.Label(left, text="THE DARK RIDE", style="HeaderBig.TLabel")
        title_label.pack(anchor="w")

        self.clock_var = tk.StringVar(value=time.strftime("%H:%M:%S"))
        self.clock_label = ttk.Label(right, textvariable=self.clock_var, style="ClockBig.TLabel")
        self.clock_label.pack(anchor="e")
        
        # Data source indicator
        self.data_source_var = tk.StringVar(value="Demo Mode")
        self.data_source_label = ttk.Label(right, textvariable=self.data_source_var, style="TLabel")
        self.data_source_label.pack(anchor="e", pady=(4, 0))
        
        # Status indicator (moved from footer to header)
        self.status_var = tk.StringVar(value="Systems nominal")
        self.status_label = ttk.Label(left, textvariable=self.status_var, style="TLabel")
        self.status_label.pack(anchor="w", pady=(4, 0))

    def _build_metric_card(self, row: int, col: int, key: str, title: str, unit: str):
        card = tk.Frame(self.grid_frame, bg=self.card_bg, highlightbackground=self.primary_color, highlightcolor=self.primary_color, highlightthickness=2, bd=0)
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

        # Make grid responsive
        self.grid_frame.grid_columnconfigure(col, weight=1, uniform="col")
        self.grid_frame.grid_rowconfigure(row, weight=1, uniform="row")

        title_label = ttk.Label(card, text=title, style="Title.TLabel")
        title_label.pack(anchor="w", padx=12, pady=(12, 4))

        value_var = tk.StringVar(value="-")
        value_label = ttk.Label(card, textvariable=value_var, style="Metric.TLabel")
        value_label.pack(anchor="w", padx=12)

        unit_label = ttk.Label(card, text=unit, style="Unit.TLabel")
        unit_label.pack(anchor="w", padx=12, pady=(0, 12))

        self.metric_cards[key] = {
            "frame": card,
            "value_var": value_var,
        }

    def _build_footer(self):
        # Footer is now empty since status moved to header
        pass

    def _build_detail_page(self, parent: tk.Frame, title: str, key: str, unit: str):
        header = tk.Frame(parent, bg=self["bg"])
        header.pack(fill=tk.X, padx=16, pady=(12, 6))
        title_label = ttk.Label(header, text=f"{title}", style="Header.TLabel")
        title_label.pack(anchor="center")

        # For speed page, use a canvas to draw PNG logo with centered text and animation
        if key == "speed":
            canvas = tk.Canvas(parent, bg="#000000", highlightthickness=0, bd=0)
            canvas.pack(expand=True, fill=tk.BOTH)
            self.speed_canvas = canvas
            self._speed_logo_tk = None
            def _on_speed_resize(_e=None):
                self._redraw_speed_canvas()
            canvas.bind("<Configure>", _on_speed_resize)
        else:
            body = tk.Frame(parent, bg=self["bg"])
            body.pack(expand=True, fill=tk.BOTH)

            value_var = tk.StringVar(value="-")
            value_label = ttk.Label(body, textvariable=value_var, style="Metric.TLabel")
            value_label.pack(expand=True)

            unit_label = ttk.Label(body, text=unit, style="Unit.TLabel")
            unit_label.pack(pady=(0, 32))

            # map detail key to var for updates
            if not hasattr(self, "detail_vars"):
                self.detail_vars = {}
            self.detail_vars[key] = value_var

        footer = tk.Frame(parent, bg=self["bg"])
        footer.pack(fill=tk.X, padx=16, pady=(6, 12))

    def _build_statistics_page(self, parent: tk.Frame):
        """Build the statistics page with max values and reset button"""
        header = tk.Frame(parent, bg=self["bg"])
        header.pack(fill=tk.X, padx=16, pady=(12, 6))
        title_label = ttk.Label(header, text="Statistics", style="Header.TLabel")
        title_label.pack(anchor="center")

        # Statistics display area
        stats_frame = tk.Frame(parent, bg=self["bg"])
        stats_frame.pack(expand=True, fill=tk.BOTH, padx=16, pady=(16, 8))

        # Create statistics labels
        self.stats_vars = {}
        stats_items = [
            ("max_speed", "Max Speed", "mph"),
            ("total_distance", "Total Distance", "km"),
            ("max_cornering", "Max Cornering Force", "g"),
            ("max_braking", "Max Braking Force", "g"),
            ("session_time", "Session Time", "hours")
        ]

        for i, (key, label, unit) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            stat_frame = tk.Frame(stats_frame, bg=self["bg"])
            stat_frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            
            # Make grid responsive
            stats_frame.grid_columnconfigure(col, weight=1, uniform="stat_col")
            stats_frame.grid_rowconfigure(row, weight=1, uniform="stat_row")
            
            # Label
            label_widget = ttk.Label(stat_frame, text=label, style="Title.TLabel")
            label_widget.pack(anchor="w", padx=12, pady=(12, 4))
            
            # Value
            value_var = tk.StringVar(value="-")
            value_label = ttk.Label(stat_frame, textvariable=value_var, style="Metric.TLabel")
            value_label.pack(anchor="w", padx=12)
            
            # Unit
            unit_label = ttk.Label(stat_frame, text=unit, style="Unit.TLabel")
            unit_label.pack(anchor="w", padx=12, pady=(0, 12))
            
            self.stats_vars[key] = value_var

        # Add reset button as a 6th statistic in the grid
        reset_frame = tk.Frame(stats_frame, bg=self["bg"])
        reset_frame.grid(row=2, column=1, sticky="nsew", padx=8, pady=8)
        
        # Label
        reset_label = ttk.Label(reset_frame, text="Reset Data", style="Title.TLabel")
        reset_label.pack(anchor="w", padx=12, pady=(12, 4))
        
        # Create a canvas-based button to completely override system styling
        reset_btn = tk.Canvas(
            reset_frame,
            width=200,
            height=60,
            bg="#FF0000",
            highlightthickness=0,
            relief=tk.RAISED,
            bd=2
        )
        
        # Draw the button background and text
        reset_btn.create_rectangle(0, 0, 200, 60, fill="#FF0000", outline="#CC0000", width=2)
        reset_btn.create_text(100, 30, text="RESET", fill="#FFFFFF", font=("Helvetica", 24, "bold"))
        
        # Add click functionality
        def on_click(event):
            self._reset_statistics()
        
        def on_enter(event):
            reset_btn.configure(bg="#CC0000")
            reset_btn.itemconfig(1, fill="#CC0000")  # Change background rectangle
        
        def on_leave(event):
            reset_btn.configure(bg="#FF0000")
            reset_btn.itemconfig(1, fill="#FF0000")  # Change background rectangle
        
        reset_btn.bind("<Button-1>", on_click)
        reset_btn.bind("<Enter>", on_enter)
        reset_btn.bind("<Leave>", on_leave)
        reset_btn.configure(cursor="hand2")
        reset_btn.pack(anchor="w", padx=12, pady=(0, 12))
        
        # Store reference to reset button for page cycling logic
        self.reset_button = reset_btn

    def _reset_statistics(self):
        """Reset all statistics"""
        self.reset_statistics()
        # Update display immediately
        self._update_statistics()
        
        # Show confirmation message
        self.status_var.set("Statistics reset successfully!")
        
        # Reset status message after 3 seconds
        self.after(3000, lambda: self.status_var.set("Systems nominal"))

    def _redraw_speed_canvas(self):
        if not hasattr(self, "speed_canvas"):
            return
        c = self.speed_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 0 or h <= 0:
            return
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill="#000000", outline="")
        # Determine current speed text (mph) if available
        speed_text = getattr(self, "_last_speed_text", "-")
        # Choose base image: logo if available, else draw circle
        if self._logo_image_base is not None and ImageTk is not None:
            # Fixed scale based on screen size, not speed
            base_scale = min(w, h) * 1.5
            img = self._logo_image_base.copy()
            
            # Calculate target size maintaining aspect ratio
            img_w, img_h = img.size
            aspect_ratio = img_w / img_h
            
            if aspect_ratio > 1:  # Wider than tall
                target_w = int(base_scale)
                target_h = int(base_scale / aspect_ratio)
            else:  # Taller than wide
                target_h = int(base_scale)
                target_w = int(base_scale * aspect_ratio)
            
            # Ensure minimum size
            target_w = max(64, target_w)
            target_h = max(64, target_h)
            
            img.thumbnail((target_w, target_h), Image.LANCZOS)
            self._speed_logo_tk = ImageTk.PhotoImage(img)
            c.create_image(w // 2, h // 2, image=self._speed_logo_tk)
        else:
            r = int(min(w, h) * 0.3)
            c.create_oval(w//2 - r, h//2 - r, w//2 + r, h//2 + r, outline=self.primary_color, width=3)

        # Draw centered speed text
        font_size = max(32, int(min(w, h) * 0.12))
        try:
            c.create_text(w // 2, h // 2, text=speed_text, fill=self.primary_color, font=("Helvetica", font_size, "bold"))
        except Exception:
            c.create_text(w // 2, h // 2, text=speed_text, fill=self.primary_color)

    def _show_page(self, idx: int):
        # hide all
        for frame in self._pages.values():
            frame.place_forget()
            frame.pack_forget()
        # show target
        frame = self._pages.get(idx)
        if frame is None:
            return
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._current_page_idx = idx

    def _cycle_page(self, event=None):
        # Don't cycle if clicking on the reset button
        if (event and hasattr(self, 'reset_button') and 
            self.reset_button.winfo_exists() and
            self.reset_button.winfo_containing(event.x_root, event.y_root) == self.reset_button):
            return
        
        next_idx = (self._current_page_idx + 1) % len(self._pages)
        self._show_page(next_idx)

    def start(self):
        self._schedule_update()
        self.mainloop()

    def stop(self):
        self._stop_event.set()

    # Periodic update
    def _schedule_update(self):
        if self._stop_event.is_set():
            return
        self._update_clock()
        self._update_metrics()
        self.after(self._update_interval_ms, self._schedule_update)

    def _update_clock(self):
        self.clock_var.set(time.strftime("%H:%M:%S"))
        # Update data source indicator
        self.data_source_var.set(self.get_data_source())

    def _update_metrics(self):
        try:
            speed = self.get_speed()
            altitude = self.get_altitude()
            temperature = self.get_temperature()
            ax, ay, az = self.get_accel()

            # Convert speed km/h -> mph
            speed_mph = speed * 0.621371
            self.metric_cards["speed"]["value_var"].set(f"{speed_mph:0.1f}")
            self.metric_cards["altitude"]["value_var"].set(f"{altitude:0.0f}")
            self.metric_cards["temperature"]["value_var"].set(f"{temperature:0.1f}")
            self.metric_cards["accel"]["value_var"].set(f"{ax:0.2f}, {ay:0.2f}, {az:0.2f}")

            # Update detail pages if present
            if hasattr(self, "detail_vars"):
                if "speed" in self.detail_vars:
                    self.detail_vars["speed"].set(f"{speed_mph:0.1f}")
                if "altitude" in self.detail_vars:
                    self.detail_vars["altitude"].set(f"{altitude:0.0f}")
                if "temperature" in self.detail_vars:
                    self.detail_vars["temperature"].set(f"{temperature:0.1f}")
                if "accel" in self.detail_vars:
                    self.detail_vars["accel"].set(f"{ax:0.2f}, {ay:0.2f}, {az:0.2f}")

            # Update speed canvas text and animation state
            self._last_speed_value = float(speed_mph)
            self._last_speed_text = f"{speed_mph:0.1f}"
            if hasattr(self, "speed_canvas"):
                self._redraw_speed_canvas()

            # Update statistics page if it exists
            if hasattr(self, "stats_vars"):
                self._update_statistics()

            # Check sensor health and update status
            sensor_status = self.get_sensor_status()
            failed_sensors = [name for name, status in sensor_status.items() if not status['healthy']]
            
            if failed_sensors:
                self.status_var.set(f"Sensor errors: {', '.join(failed_sensors)}")
            else:
                self.status_var.set("Systems nominal")
                
        except Exception as exc:  # visible feedback on screen
            self.status_var.set(f"Error: {exc}")

    def _update_statistics(self):
        """Update statistics display"""
        try:
            stats = self.get_statistics()
            
            # Convert speed from km/h to mph
            max_speed_mph = stats['max_speed_kmh'] * 0.621371
            
            self.stats_vars["max_speed"].set(f"{max_speed_mph:0.1f}")
            self.stats_vars["total_distance"].set(f"{stats['total_distance_km']:0.2f}")
            self.stats_vars["max_cornering"].set(f"{stats['max_cornering_force_g']:0.2f}")
            self.stats_vars["max_braking"].set(f"{stats['max_braking_force_g']:0.2f}")
            self.stats_vars["session_time"].set(f"{stats['session_duration_hours']:0.1f}")
        except Exception as e:
            print(f"Statistics update error: {e}")


def run_dashboard(get_speed: Callable[[], float], get_altitude: Callable[[], float], get_temperature: Callable[[], float], get_accel: Callable[[], tuple[float, float, float]], get_sensor_status: Callable[[], dict], get_data_source: Callable[[], str], get_statistics: Callable[[], dict], reset_statistics: Callable[[], None], *, fullscreen: bool = True):
    app = DarkRideDashboard(get_speed, get_altitude, get_temperature, get_accel, get_sensor_status, get_data_source, get_statistics, reset_statistics, fullscreen=fullscreen)
    app.start()


