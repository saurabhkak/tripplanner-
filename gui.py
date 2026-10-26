"""Tkinter desktop interface for the Multi-Modal Trip Planner.

Run with ``python gui.py``. Transport lookup and DynamoDB persistence are
delegated to the existing ``transport`` and ``storage`` modules.
"""

import queue
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from storage import TABLE_NAME, load_bookings, save_booking
from transport import GEOAPIFY_API_KEY_ENV, geoapify_enabled, get_options


BG = "#f4f6fa"
PANEL = "#ffffff"
INK = "#172033"
MUTED = "#748096"
NAV = "#111b2e"
ACCENT = "#4263eb"
ACCENT_DARK = "#3451cf"
TEAL = "#12a594"
LINE = "#e6eaf1"
PALE_BLUE = "#edf2ff"
ERROR = "#b42318"


class TripPlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wayfarer — Trip Planner")
        self.root.geometry("1120x760")
        self.root.minsize(900, 650)
        self.root.configure(bg=BG)

        self.results = None
        self.selected_mode = None
        self.bookings = []
        self.worker_queue = queue.Queue()
        self.loading = False
        self.active_page = None
        self.page_view_id = 0

        self._configure_styles()
        self._build_shell()
        self.show_page("plan")
        self.root.after(100, self._poll_workers)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 23), foreground=INK)
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 13), foreground=INK)
        style.configure("CardTitle.TLabel", font=("Segoe UI Semibold", 12), foreground=INK)
        style.configure("Fare.TLabel", font=("Segoe UI Semibold", 18), foreground=INK)
        style.configure("TEntry", padding=(12, 11), fieldbackground="#fbfcfe", font=("Segoe UI", 11))
        style.configure("Treeview", rowheight=38, font=("Segoe UI", 10), background=PANEL,
                        fieldbackground=PANEL, foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9),
                        background="#f5f7fb", foreground=MUTED, relief="flat", padding=10)
        style.map("Treeview", background=[("selected", PALE_BLUE)], foreground=[("selected", INK)])
        style.configure("TProgressbar", troughcolor="#e9edf5", background=ACCENT,
                        bordercolor="#e9edf5", lightcolor=ACCENT, darkcolor=ACCENT)

    def _build_shell(self):
        self.sidebar = tk.Frame(self.root, bg=NAV, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=NAV)
        brand.pack(fill="x", padx=22, pady=(28, 34))
        tk.Label(brand, text="✦", bg="#273963", fg="#a9baff", font=("Segoe UI", 16, "bold"),
                 width=2, height=1).pack(side="left", padx=(0, 10))
        tk.Label(brand, text="wayfarer", bg=NAV, fg="white", font=("Segoe UI Semibold", 17)).pack(side="left")

        tk.Label(self.sidebar, text="WORKSPACE", bg=NAV, fg="#8490a5",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=24, pady=(0, 10))
        self.nav_buttons = {}
        for key, label, icon in (("plan", "Plan a trip", "⌁"), ("bookings", "My bookings", "▤")):
            button = tk.Button(self.sidebar, text=f"  {icon}    {label}", anchor="w", relief="flat",
                               bd=0, padx=14, pady=12, cursor="hand2", font=("Segoe UI", 10),
                               bg=NAV, fg="#b7c1d2", activebackground="#202e49",
                               activeforeground="white", command=lambda k=key: self.show_page(k))
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = button

        spacer = tk.Frame(self.sidebar, bg=NAV)
        spacer.pack(fill="both", expand=True)
        status_card = tk.Frame(self.sidebar, bg="#1a2740", padx=13, pady=13)
        status_card.pack(fill="x", padx=14, pady=(0, 17))
        tk.Label(status_card, text="CONNECTIONS", bg="#1a2740", fg="#8490a5",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(0, 9))
        geo_status = "Geoapify live routes" if geoapify_enabled() else "Static routes available"
        self._sidebar_status(status_card, "●", geo_status, TEAL if geoapify_enabled() else "#e9b949")
        self._sidebar_status(status_card, "●", "DynamoDB storage", "#78a1ff")
        tk.Label(self.sidebar, text="MULTI-MODAL TRIP PLANNER", bg=NAV, fg="#66748a",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=25, pady=(0, 16))

        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.header = tk.Frame(self.content, bg=BG)
        self.header.pack(fill="x", padx=36, pady=(24, 10))
        self.header_title = tk.Label(self.header, text="Good to see you", bg=BG, fg=INK,
                                     font=("Segoe UI Semibold", 12))
        self.header_title.pack(side="left")
        self.connection_badge = tk.Label(self.header, text="  ●  DynamoDB · AWS CLI profile  ",
                                         bg="#e8f7f4", fg="#127a6e", font=("Segoe UI", 9), pady=7)
        self.connection_badge.pack(side="right")
        viewport = tk.Frame(self.content, bg=BG)
        viewport.pack(fill="both", expand=True, padx=(36, 24), pady=(5, 22))
        self.page_canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, bd=0)
        self.page_scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_scrollbar.pack(side="right", fill="y")
        self.page_canvas.pack(side="left", fill="both", expand=True)
        self.page = tk.Frame(self.page_canvas, bg=BG)
        self.page_window = self.page_canvas.create_window((0, 0), window=self.page, anchor="nw")
        self.page.bind("<Configure>", self._update_scroll_region)
        self.page_canvas.bind("<Configure>", self._fit_page_width)
        self.page_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _update_scroll_region(self, _event=None):
        self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))

    def _fit_page_width(self, event):
        self.page_canvas.itemconfigure(self.page_window, width=event.width)

    def _on_mousewheel(self, event):
        if event.delta:
            units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
            self.page_canvas.yview_scroll(units, "units")

    @staticmethod
    def _sidebar_status(parent, icon, text, color):
        row = tk.Frame(parent, bg="#1a2740")
        row.pack(fill="x", pady=3)
        tk.Label(row, text=icon, bg="#1a2740", fg=color, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(row, text=text, bg="#1a2740", fg="#d7deea", font=("Segoe UI", 9)).pack(side="left", padx=7)

    def show_page(self, name):
        self.active_page = name
        self.page_view_id += 1
        for child in self.page.winfo_children():
            child.destroy()
        for key, button in self.nav_buttons.items():
            button.configure(bg="#273754" if key == name else NAV,
                             fg="white" if key == name else "#b7c1d2")
        if name == "plan":
            self._build_plan_page()
        else:
            self._build_bookings_page()
        self.page_canvas.yview_moveto(0)

    def _build_plan_page(self):
        tk.Label(self.page, text="Plan your next trip", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 25)).pack(anchor="w", pady=(4, 2))
        tk.Label(self.page, text="Compare ways to get there, then book your preferred route.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 19))

        search = tk.Frame(self.page, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        search.pack(fill="x", pady=(0, 18))
        fields = tk.Frame(search, bg=PANEL)
        fields.pack(fill="x", padx=18, pady=(15, 12))
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(2, weight=1)
        self.source_var = tk.StringVar()
        self.destination_var = tk.StringVar()
        self._place_entry(fields, 0, "FROM", "e.g. Mumbai", self.source_var)
        swap = tk.Button(fields, text="⇄", command=self._swap_cities, bg="#f2f5fa", fg=ACCENT,
                         relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 17), width=3)
        swap.grid(row=1, column=1, padx=14, pady=(3, 0))
        self._place_entry(fields, 2, "TO", "e.g. Pune", self.destination_var)
        action_row = tk.Frame(search, bg=PANEL)
        action_row.pack(fill="x", padx=18, pady=(0, 14))
        self.search_button = self._button(action_row, "Find routes  →", self._search_routes, primary=True)
        self.search_button.pack(side="right")
        self.progress = ttk.Progressbar(action_row, mode="indeterminate", length=145)
        self.progress.pack(side="right", padx=(0, 12), pady=9)
        self.progress.pack_forget()
        self.loading_label = tk.Label(action_row, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.loading_label.pack(side="right", padx=10)

        self.results_heading = tk.Frame(self.page, bg=BG)
        self.results_heading.pack(fill="x", pady=(2, 10))
        tk.Label(self.results_heading, text="Available options", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 14)).pack(side="left")
        self.results_hint = tk.Label(self.results_heading, text="Enter a route to compare transport",
                                     bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.results_hint.pack(side="right")

        self.cards_area = tk.Frame(self.page, bg=BG)
        self.cards_area.pack(fill="both", expand=True)
        self._render_empty_state()

        self.confirm_bar = tk.Frame(self.page, bg=BG)
        self.confirm_bar.pack(fill="x", pady=(10, 0))
        self.selection_text = tk.Label(self.confirm_bar, text="Choose an option to continue",
                                       bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.selection_text.pack(side="left")
        self.book_button = self._button(self.confirm_bar, "Confirm booking", self._confirm_booking, primary=True)
        self.book_button.pack(side="right")
        self.book_button.configure(state="disabled")

    def _place_entry(self, parent, column, title, placeholder, variable):
        field = tk.Frame(parent, bg=PANEL)
        field.grid(row=0, column=column, sticky="ew")
        tk.Label(field, text=title, bg=PANEL, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", pady=(0, 5))
        entry = ttk.Entry(field, textvariable=variable)
        entry.pack(fill="x", ipady=1)
        entry.bind("<Return>", lambda _event: self._search_routes())

    def _render_empty_state(self):
        for child in self.cards_area.winfo_children():
            child.destroy()
        empty = tk.Frame(self.cards_area, bg="#eef2f8", padx=24, pady=22)
        empty.pack(fill="both", expand=True)
        tk.Label(empty, text="✦", bg="#dfe7fb", fg=ACCENT, font=("Segoe UI", 19),
                 width=3, height=1).pack(anchor="w", pady=(0, 11))
        tk.Label(empty, text="Your route, at a glance", bg="#eef2f8", fg=INK,
                 font=("Segoe UI Semibold", 15)).pack(anchor="w")
        tk.Label(empty, text="Search two cities to see travel time, distance and estimated fares\n"
                 "across bus, train, flight and cab options.", bg="#eef2f8", fg=MUTED,
                 justify="left", font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 15))
        examples = tk.Frame(empty, bg="#eef2f8")
        examples.pack(anchor="w")
        for pair in (("Mumbai", "Pune"), ("Mumbai", "Delhi"), ("Pune", "Goa")):
            chip = tk.Button(examples, text=f"{pair[0]}  →  {pair[1]}",
                             command=lambda p=pair: self._use_example(*p), bg=PANEL, fg="#46536a",
                             relief="flat", bd=0, padx=11, pady=7, cursor="hand2",
                             font=("Segoe UI", 9))
            chip.pack(side="left", padx=(0, 8))

    def _use_example(self, source, destination):
        self.source_var.set(source)
        self.destination_var.set(destination)
        self._search_routes()

    def _swap_cities(self):
        source, destination = self.source_var.get(), self.destination_var.get()
        self.source_var.set(destination)
        self.destination_var.set(source)

    def _search_routes(self):
        if self.loading:
            return
        source, destination = self.source_var.get().strip(), self.destination_var.get().strip()
        if not source or not destination:
            messagebox.showinfo("Add your route", "Enter both a starting city and a destination.", parent=self.root)
            return
        if source.casefold() == destination.casefold():
            messagebox.showinfo("Choose two cities", "Your starting point and destination need to be different.", parent=self.root)
            return
        self.loading = True
        self.search_button.configure(state="disabled")
        self.progress.pack(side="right", padx=(0, 12), pady=9)
        self.progress.start(12)
        self.loading_label.configure(text="Finding routes…")
        self._clear_results()
        self._run_async("routes", lambda: get_options(source, destination))

    def _clear_results(self):
        self.results = None
        self.selected_mode = None
        self.book_button.configure(state="disabled")
        self.selection_text.configure(text="Choose an option to continue")
        for child in self.cards_area.winfo_children():
            child.destroy()

    def _render_options(self, options):
        self._clear_results()
        self.results = options
        self.results_hint.configure(text=f"{self.source_var.get().title()}  →  {self.destination_var.get().title()}")
        if not options:
            self._render_empty_state()
            if not geoapify_enabled():
                detail = "No demo route matched. Add a Geoapify key for live route lookup."
            else:
                detail = "No route was returned. Check the city names or Geoapify access."
            messagebox.showinfo("No routes found", detail, parent=self.root)
            return
        modes = list(options.items())
        for index, (mode, details) in enumerate(modes):
            row, col = divmod(index, 2)
            self.cards_area.grid_columnconfigure(col, weight=1, uniform="routecard")
            self.cards_area.grid_rowconfigure(row, weight=1, uniform="routecard")
            self._make_option_card(mode, details, row, col)
        if len(modes) == 1:
            self.cards_area.grid_columnconfigure(1, weight=1)

    def _make_option_card(self, mode, details, row, col):
        card = tk.Frame(self.cards_area, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        card.mode = mode
        card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0),
                  pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        top = tk.Frame(card, bg=PANEL)
        top.pack(fill="x", padx=15, pady=(13, 8))
        icons = {"bus": "▰", "train": "▤", "flight": "✈", "cab": "⌑"}
        tk.Label(top, text=icons.get(mode, "●"), bg=PALE_BLUE, fg=ACCENT,
                 font=("Segoe UI", 14), width=3, height=1).pack(side="left")
        name_box = tk.Frame(top, bg=PANEL)
        name_box.pack(side="left", padx=10)
        tk.Label(name_box, text=mode.title(), bg=PANEL, fg=INK,
                 font=("Segoe UI Semibold", 12)).pack(anchor="w")
        tk.Label(name_box, text=details.get("source", "Estimated route"), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        tk.Label(card, text=f"Rs. {details['fare']:,}", bg=PANEL, fg=INK,
                 font=("Segoe UI Semibold", 19)).pack(anchor="w", padx=16, pady=(0, 7))
        meta = tk.Frame(card, bg=PANEL)
        meta.pack(fill="x", padx=16, pady=(0, 12))
        for label, value in (("TRAVEL TIME", details.get("time", "—")),
                             ("DISTANCE", details.get("distance", "N/A"))):
            cell = tk.Frame(meta, bg="#f7f8fb", padx=9, pady=7)
            cell.pack(side="left", fill="x", expand=True, padx=(0, 7))
            tk.Label(cell, text=label, bg="#f7f8fb", fg=MUTED,
                     font=("Segoe UI Semibold", 7)).pack(anchor="w")
            tk.Label(cell, text=value, bg="#f7f8fb", fg=INK,
                     font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(3, 0))
        choose = tk.Button(card, text="Select this option", command=lambda m=mode: self._select_mode(m),
                           bg="#f3f5fb", fg=ACCENT, activebackground=PALE_BLUE,
                           relief="flat", bd=0, cursor="hand2", font=("Segoe UI Semibold", 9), pady=8)
        choose.pack(fill="x", padx=16, pady=(0, 14))
        card.choose_button = choose

    def _select_mode(self, mode):
        self.selected_mode = mode
        self.book_button.configure(state="normal")
        details = self.results[mode]
        self.selection_text.configure(text=f"{mode.title()} selected  ·  Rs. {details['fare']:,}", fg=INK)
        for card in self.cards_area.winfo_children():
            selected = getattr(card, "mode", None) == mode
            card.configure(highlightbackground=ACCENT if selected else LINE)
            if hasattr(card, "choose_button"):
                card.choose_button.configure(
                    text="Selected ✓" if selected else "Select this option",
                    bg="#e7edff" if selected else "#f3f5fb",
                )

    def _confirm_booking(self):
        if not self.selected_mode or not self.results:
            return
        source, destination = self.source_var.get().strip(), self.destination_var.get().strip()
        mode = self.selected_mode
        details = self.results[mode]
        summary = (f"{source.title()}  →  {destination.title()}\n\n"
                   f"{mode.title()}  ·  {details.get('time', '—')}  ·  {details.get('distance', 'N/A')}\n"
                   f"Estimated fare: Rs. {details['fare']:,}\n\nSave this booking to DynamoDB?")
        if not messagebox.askyesno("Confirm your trip", summary, parent=self.root):
            return
        self.book_button.configure(state="disabled", text="Saving…")
        self._run_async("save", lambda: save_booking(source, destination, mode, details))

    def _build_bookings_page(self):
        tk.Label(self.page, text="My bookings", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 25)).pack(anchor="w", pady=(4, 2))
        top = tk.Frame(self.page, bg=BG)
        top.pack(fill="x", pady=(0, 18))
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "AWS profile default"
        tk.Label(top, text=f"Saved journeys · {TABLE_NAME} · {region}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        refresh = self._button(top, "↻  Refresh", self._refresh_bookings)
        refresh.pack(side="right")

        panel = tk.Frame(self.page, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        columns = ("route", "mode", "time", "distance", "fare", "date")
        self.booking_tree = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        headings = (("route", "ROUTE", 220), ("mode", "MODE", 90), ("time", "TIME", 110),
                    ("distance", "DISTANCE", 110), ("fare", "FARE", 110), ("date", "BOOKED", 170))
        for col, text, width in headings:
            self.booking_tree.heading(col, text=text)
            self.booking_tree.column(col, width=width, minwidth=70, anchor="w")
        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.booking_tree.yview)
        self.booking_tree.configure(yscrollcommand=scroll.set)
        self.booking_tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.booking_tree.bind("<<TreeviewSelect>>", self._show_booking_detail)

        self.booking_status = tk.Label(self.page, text="Loading bookings…", bg=BG, fg=MUTED,
                                       font=("Segoe UI", 9), anchor="w")
        self.booking_status.pack(fill="x", pady=(10, 4))
        self.detail_label = tk.Label(self.page, text="Select a booking to see its full details.",
                                     bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.detail_label.pack(fill="x")
        self._refresh_bookings()

    def _refresh_bookings(self):
        self.booking_status.configure(text="Loading bookings…", fg=MUTED)
        for item in self.booking_tree.get_children():
            self.booking_tree.delete(item)
        self._run_async("bookings", load_bookings)

    def _show_booking_detail(self, _event=None):
        selection = self.booking_tree.selection()
        if not selection:
            return
        booking = self.bookings[int(selection[0])]
        self.detail_label.configure(
            text=f"Booking ID: {booking.get('id', booking.get('booking_id', '—'))}    ·    "
                 f"Source: {booking.get('data_source', '—')}    ·    "
                 f"Booked at: {booking.get('booked_at', '—')}", fg="#536078")

    def _run_async(self, task_name, function):
        view_id = self.page_view_id

        def worker():
            try:
                result = function()
                self.worker_queue.put((task_name, result, None, view_id))
            except Exception as exc:  # Surface backend and network errors in the UI.
                self.worker_queue.put((task_name, None, exc, view_id))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_workers(self):
        try:
            while True:
                task, result, error, view_id = self.worker_queue.get_nowait()
                if task == "routes":
                    if view_id != self.page_view_id or self.active_page != "plan":
                        self.loading = False
                        continue
                    self.loading = False
                    self.progress.stop()
                    self.progress.pack_forget()
                    self.loading_label.configure(text="")
                    self.search_button.configure(state="normal")
                    if error:
                        self._render_empty_state()
                        messagebox.showerror("Route lookup failed", self._friendly_error(error), parent=self.root)
                    else:
                        self._render_options(result)
                elif task == "save":
                    if view_id == self.page_view_id and self.active_page == "plan":
                        self.book_button.configure(state="normal", text="Confirm booking")
                    if error:
                        messagebox.showerror("Booking could not be saved", self._friendly_error(error), parent=self.root)
                    else:
                        messagebox.showinfo("Booking saved", "Your booking was saved to DynamoDB.", parent=self.root)
                        if view_id == self.page_view_id and self.active_page == "plan":
                            self.book_button.configure(state="disabled")
                            self.selection_text.configure(text="Booking confirmed and saved", fg=TEAL)
                        elif self.active_page == "bookings":
                            self._refresh_bookings()
                elif task == "bookings":
                    if view_id != self.page_view_id or self.active_page != "bookings":
                        continue
                    if error:
                        self.booking_status.configure(text=self._friendly_error(error), fg=ERROR)
                    else:
                        self.bookings = result
                        for item in self.booking_tree.get_children():
                            self.booking_tree.delete(item)
                        if not result:
                            self.booking_status.configure(
                                text=f"No items found in {TABLE_NAME}. Check that the app and console use the same AWS account and Region.",
                                fg=MUTED,
                            )
                        else:
                            for index, booking in enumerate(result):
                                route = f"{booking.get('source', '—')}  →  {booking.get('destination', '—')}"
                                booked_at = str(booking.get("booked_at", "—")).replace("T", " ")[:16]
                                fare = booking.get("fare", "—")
                                if isinstance(fare, (int, float)):
                                    fare = f"Rs. {fare:,}"
                                self.booking_tree.insert("", "end", iid=str(index), values=(
                                    route, booking.get("mode", "—"), booking.get("time", "—"),
                                    booking.get("distance", "N/A"), fare, booked_at))
                            self.booking_status.configure(text=f"{len(result)} booking(s) loaded", fg=TEAL)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_workers)

    @staticmethod
    def _friendly_error(error):
        message = str(error)
        if "NoCredentials" in message or "credentials" in message.lower():
            return "AWS credentials are unavailable. Sign in with `aws login`, then restart this app."
        if "ResourceNotFoundException" in message or "nonexistent table" in message.lower():
            return "TripBookings was not found. Check the table name and AWS Region."
        if "AccessDenied" in message or "not authorized" in message.lower():
            return "AWS denied this operation. Grant your CLI identity access to the TripBookings table."
        return message

    @staticmethod
    def _button(parent, text, command, primary=False):
        bg = ACCENT if primary else PANEL
        fg = "white" if primary else "#46536a"
        button = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                           activebackground=ACCENT_DARK if primary else "#eef1f7",
                           activeforeground="white" if primary else INK,
                           relief="flat", bd=0, padx=17, pady=10, cursor="hand2",
                           font=("Segoe UI Semibold", 9), highlightthickness=0)
        if primary:
            button.configure(disabledforeground="#d8dffc")
        return button


def main():
    root = tk.Tk()
    TripPlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
