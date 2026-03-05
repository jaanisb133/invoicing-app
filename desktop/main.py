"""
Veggie Invoice Manager - Main Application
A simple invoicing and stock management tool for vegetable trading.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import os
import subprocess
import sys

import database as db

# --- Constants ---
APP_TITLE = "Pavadzīmju Pārvaldnieks"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 850
FONT_LARGE = ("Segoe UI", 14)
FONT_MEDIUM = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 11, "bold")

UNITS = ["kg", "gab", "kaste", "iepak.", "l"]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(800, 600)

        # Initialize database
        db.init_db()

        # Configure styles
        self.configure(bg="#f0f0f0")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Nav.TButton", font=FONT_BUTTON, padding=(20, 12))
        style.configure("Action.TButton", font=FONT_MEDIUM, padding=(15, 8))
        style.configure("Treeview", font=FONT_SMALL, rowheight=28,
                        borderwidth=1, relief="solid")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        borderwidth=1, relief="solid")
        style.layout("Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ])
        style.configure("TLabel", font=FONT_MEDIUM)
        style.configure("TEntry", font=FONT_MEDIUM)
        style.configure("Header.TLabel", font=FONT_LARGE)

        # Treeview with visible column separators
        self._tree_counter = 0

        # Layout: sidebar + content
        self.sidebar = tk.Frame(self, bg="#2c3e50", width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.content = tk.Frame(self, bg="#f0f0f0")
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollable content area
        self._scroll_canvas = None
        self._scroll_frame = None

        # Navigation buttons
        nav_items = [
            ("Iestatījumi", self.show_settings),
            ("Produkti", self.show_products),
            ("Klienti", self.show_clients),
            ("Jauns dokuments", self.show_new_document),
            ("Dokumenti", self.show_documents),
            ("Noliktava", self.show_stock),
        ]

        tk.Label(self.sidebar, text=APP_TITLE, font=("Segoe UI", 13, "bold"),
                 bg="#2c3e50", fg="white", wraplength=180, pady=15).pack(fill=tk.X)

        for text, command in nav_items:
            btn = tk.Button(
                self.sidebar, text=text, command=command,
                font=FONT_MEDIUM, bg="#34495e", fg="white",
                activebackground="#4a6785", activeforeground="white",
                bd=0, pady=12, anchor="w", padx=15,
                cursor="hand2"
            )
            btn.pack(fill=tk.X, padx=5, pady=2)

        # Show settings by default
        self.show_settings()

    def clear_content(self):
        """Clear the content area."""
        for widget in self.content.winfo_children():
            widget.destroy()
        return self.content

    def style_treeview(self, tree):
        """Add alternating row colors to a treeview for better readability."""
        tree.tag_configure("oddrow", background="#ffffff")
        tree.tag_configure("evenrow", background="#f5f5f5")
        tree.tag_configure("zero", foreground="gray", background="#ffffff")
        tree.tag_configure("positive", foreground="green", background="#ffffff")
        tree.tag_configure("negative", foreground="red", background="#ffffff")
        tree.tag_configure("zero_even", foreground="gray", background="#f5f5f5")
        tree.tag_configure("positive_even", foreground="green", background="#f5f5f5")
        tree.tag_configure("negative_even", foreground="red", background="#f5f5f5")

    # =========================================================================
    # SETTINGS
    # =========================================================================
    def show_settings(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Uzņēmuma iestatījumi", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        settings_fields = [
            ("company_name", "Uzņēmuma nosaukums"),
            ("reg_number", "Reģistrācijas numurs"),
            ("vat_number", "PVN numurs"),
            ("legal_address", "Juridiskā adrese"),
            ("bank_name", "Bankas nosaukums"),
            ("bank_account", "Bankas konts"),
            ("phone", "Tālrunis"),
            ("email", "E-pasts"),
            ("default_vat_rate", "PVN likme (%)"),
        ]

        doc_settings_fields = [
            ("buy_doc_name", "Pirkuma dok. nosaukums", "PIRKUMA PAVADZĪME"),
            ("buy_doc_prefix", "Pirkuma dok. prefikss", "PIR"),
            ("sell_doc_name", "Pārdošanas dok. nosaukums", "PĀRDOŠANAS PAVADZĪME"),
            ("sell_doc_prefix", "Pārdošanas dok. prefikss", "PAR"),
        ]

        entries = {}
        form_frame = tk.Frame(frame, bg="#f0f0f0")
        form_frame.pack(fill=tk.X)

        for i, (key, label) in enumerate(settings_fields):
            tk.Label(form_frame, text=label + ":", font=FONT_MEDIUM,
                     bg="#f0f0f0", anchor="w").grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            entry = tk.Entry(form_frame, font=FONT_MEDIUM, width=50)
            entry.grid(row=i, column=1, sticky="ew", pady=4)
            entry.insert(0, db.get_setting(key, "21" if key == "default_vat_rate" else ""))
            entries[key] = entry

        form_frame.columnconfigure(1, weight=1)

        # Document settings section
        sep_row = len(settings_fields)
        tk.Label(form_frame, text="", bg="#f0f0f0").grid(row=sep_row, column=0, pady=5)
        tk.Label(form_frame, text="Dokumentu iestatījumi", font=FONT_LARGE,
                 bg="#f0f0f0").grid(row=sep_row + 1, column=0, columnspan=2, sticky="w", pady=(5, 10))

        for j, (key, label, default) in enumerate(doc_settings_fields):
            row = sep_row + 2 + j
            tk.Label(form_frame, text=label + ":", font=FONT_MEDIUM,
                     bg="#f0f0f0", anchor="w").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
            entry = tk.Entry(form_frame, font=FONT_MEDIUM, width=50)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            entry.insert(0, db.get_setting(key, default))
            entries[key] = entry

        # Preview label
        preview_row = sep_row + 2 + len(doc_settings_fields)
        tk.Label(form_frame, text="", bg="#f0f0f0").grid(row=preview_row, column=0, pady=2)
        preview_label = tk.Label(form_frame, text="", font=FONT_SMALL, bg="#f0f0f0", fg="gray")
        preview_label.grid(row=preview_row + 1, column=0, columnspan=2, sticky="w")

        # Default price VAT toggle
        vat_toggle_row = preview_row + 2
        tk.Label(form_frame, text="", bg="#f0f0f0").grid(row=vat_toggle_row, column=0, pady=2)
        tk.Label(form_frame, text="Cenas ievade pēc noklusējuma:", font=FONT_MEDIUM,
                 bg="#f0f0f0", anchor="w").grid(row=vat_toggle_row + 1, column=0, sticky="w", pady=4, padx=(0, 10))
        vat_default_var = tk.StringVar(value=db.get_setting("default_price_includes_vat", "0"))
        vat_toggle_frame = tk.Frame(form_frame, bg="#f0f0f0")
        vat_toggle_frame.grid(row=vat_toggle_row + 1, column=1, sticky="w", pady=4)
        tk.Radiobutton(vat_toggle_frame, text="Bez PVN", variable=vat_default_var, value="0",
                       font=FONT_MEDIUM, bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 15))
        tk.Radiobutton(vat_toggle_frame, text="Ar PVN", variable=vat_default_var, value="1",
                       font=FONT_MEDIUM, bg="#f0f0f0").pack(side=tk.LEFT)
        entries["default_price_includes_vat"] = vat_default_var

        def update_preview(*args):
            buy_pfx = entries["buy_doc_prefix"].get().strip() or "PIR"
            sell_pfx = entries["sell_doc_prefix"].get().strip() or "PAR"
            year = datetime.datetime.now().year
            preview_label.config(
                text=f"Piemērs: Pirkums → {buy_pfx}-{year}-0001  |  Pārdošana → {sell_pfx}-{year}-0001"
            )

        for key in ["buy_doc_prefix", "sell_doc_prefix"]:
            entries[key].bind("<KeyRelease>", update_preview)
        update_preview()

        def save_settings():
            for key, widget in entries.items():
                if isinstance(widget, tk.StringVar):
                    db.set_setting(key, widget.get())
                else:
                    db.set_setting(key, widget.get().strip())
            messagebox.showinfo("Saglabāts", "Iestatījumi saglabāti!")

        btn_frame = tk.Frame(frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, pady=20)
        ttk.Button(btn_frame, text="Saglabāt", command=save_settings,
                   style="Action.TButton").pack(side=tk.LEFT)

    # =========================================================================
    # PRODUCTS
    # =========================================================================
    def show_products(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Produkti", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        # Add product form
        form_frame = tk.LabelFrame(frame, text="Pievienot / Rediģēt produktu",
                                   font=FONT_MEDIUM, bg="#f0f0f0", padx=15, pady=10)
        form_frame.pack(fill=tk.X, pady=(0, 15))

        inner = tk.Frame(form_frame, bg="#f0f0f0")
        inner.pack(fill=tk.X)

        tk.Label(inner, text="Nosaukums:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        name_entry = tk.Entry(inner, font=FONT_MEDIUM, width=30)
        name_entry.grid(row=0, column=1, padx=(0, 20))

        tk.Label(inner, text="Mērvienība:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=0, column=2, sticky="w", padx=(0, 10))
        unit_var = tk.StringVar(value=UNITS[0])
        unit_combo = ttk.Combobox(inner, textvariable=unit_var, values=UNITS,
                                  font=FONT_MEDIUM, width=10, state="readonly")
        unit_combo.grid(row=0, column=3, padx=(0, 20))

        editing_id = [None]

        def save_product():
            name = name_entry.get().strip()
            unit = unit_var.get()
            if not name:
                messagebox.showwarning("Kļūda", "Ievadiet produkta nosaukumu!")
                return
            if editing_id[0]:
                db.update_product(editing_id[0], name, unit)
                editing_id[0] = None
                add_btn.config(text="Pievienot")
            else:
                db.add_product(name, unit)
            name_entry.delete(0, tk.END)
            unit_var.set(UNITS[0])
            refresh_list()

        def cancel_edit():
            editing_id[0] = None
            name_entry.delete(0, tk.END)
            unit_var.set(UNITS[0])
            add_btn.config(text="Pievienot")

        add_btn = ttk.Button(inner, text="Pievienot", command=save_product,
                             style="Action.TButton")
        add_btn.grid(row=0, column=4, padx=(0, 5))

        cancel_btn = ttk.Button(inner, text="Atcelt", command=cancel_edit,
                                style="Action.TButton")
        cancel_btn.grid(row=0, column=5)

        # Products list
        tree_frame = tk.Frame(frame, bg="#f0f0f0")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame, columns=("id", "name", "unit"), show="headings", height=15)
        tree.heading("id", text="ID")
        tree.heading("name", text="Nosaukums")
        tree.heading("unit", text="Mērvienība")
        tree.column("id", width=50)
        tree.column("name", width=300)
        tree.column("unit", width=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.style_treeview(tree)

        def refresh_list():
            tree.delete(*tree.get_children())
            for i, p in enumerate(db.get_all_products()):
                tag = "evenrow" if i % 2 else "oddrow"
                tree.insert("", tk.END, values=(p["id"], p["name"], p["unit"]), tags=(tag,))

        def edit_selected():
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])["values"]
            editing_id[0] = vals[0]
            name_entry.delete(0, tk.END)
            name_entry.insert(0, vals[1])
            unit_var.set(vals[2])
            add_btn.config(text="Saglabāt")

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])["values"]
            if messagebox.askyesno("Dzēst?", f"Vai tiešām dzēst \"{vals[1]}\"?"):
                db.delete_product(vals[0])
                refresh_list()

        tree.bind("<Double-1>", lambda e: edit_selected())

        btn_frame = tk.Frame(frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Rediģēt", command=edit_selected,
                   style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Dzēst", command=delete_selected,
                   style="Action.TButton").pack(side=tk.LEFT)

        refresh_list()

    # =========================================================================
    # CLIENTS
    # =========================================================================
    def show_clients(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Klienti", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        # Client list
        tree_frame = tk.Frame(frame, bg="#f0f0f0")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame,
                            columns=("id", "name", "reg", "address", "phone"),
                            show="headings", height=15)
        tree.heading("id", text="ID")
        tree.heading("name", text="Nosaukums")
        tree.heading("reg", text="Reģ.Nr.")
        tree.heading("address", text="Adrese")
        tree.heading("phone", text="Tālrunis")
        tree.column("id", width=40)
        tree.column("name", width=200)
        tree.column("reg", width=120)
        tree.column("address", width=200)
        tree.column("phone", width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.style_treeview(tree)

        def refresh_clients():
            tree.delete(*tree.get_children())
            for i, c in enumerate(db.get_all_clients()):
                tag = "evenrow" if i % 2 else "oddrow"
                tree.insert("", tk.END, values=(
                    c["id"], c["name"], c["reg_number"] or "",
                    c["legal_address"] or "", c["phone"] or ""
                ), tags=(tag,))

        def open_client_form(client_id=None):
            """Open a form dialog to add/edit a client."""
            dialog = tk.Toplevel(self)
            dialog.title("Rediģēt klientu" if client_id else "Jauns klients")
            dialog.geometry("500x450")
            dialog.transient(self)
            dialog.grab_set()
            dialog.configure(bg="#f0f0f0")

            fields = [
                ("name", "Nosaukums *"),
                ("reg_number", "Reģistrācijas Nr."),
                ("vat_number", "PVN Nr."),
                ("legal_address", "Juridiskā adrese"),
                ("bank_name", "Banka"),
                ("bank_account", "Bankas konts"),
                ("contact_person", "Kontaktpersona"),
                ("phone", "Tālrunis"),
                ("email", "E-pasts"),
            ]

            entries = {}
            existing = None
            if client_id:
                existing = db.get_client(client_id)

            form = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=15)
            form.pack(fill=tk.BOTH, expand=True)

            for i, (key, label) in enumerate(fields):
                tk.Label(form, text=label + ":", font=FONT_MEDIUM,
                         bg="#f0f0f0").grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
                entry = tk.Entry(form, font=FONT_MEDIUM, width=35)
                entry.grid(row=i, column=1, sticky="ew", pady=3)
                if existing and existing[key]:
                    entry.insert(0, existing[key])
                entries[key] = entry

            form.columnconfigure(1, weight=1)

            def save():
                name = entries["name"].get().strip()
                if not name:
                    messagebox.showwarning("Kļūda", "Ievadiet klienta nosaukumu!", parent=dialog)
                    return

                kwargs = {k: e.get().strip() for k, e in entries.items()}
                if client_id:
                    db.update_client(client_id, **kwargs)
                else:
                    db.add_client(**kwargs)

                dialog.destroy()
                refresh_clients()

            btn_frame = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=10)
            btn_frame.pack(fill=tk.X)
            ttk.Button(btn_frame, text="Saglabāt", command=save,
                       style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="Atcelt", command=dialog.destroy,
                       style="Action.TButton").pack(side=tk.LEFT)

        def edit_selected():
            sel = tree.selection()
            if not sel:
                return
            client_id = tree.item(sel[0])["values"][0]
            open_client_form(client_id)

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])["values"]
            if messagebox.askyesno("Dzēst?", f"Vai tiešām dzēst \"{vals[1]}\"?"):
                db.delete_client(vals[0])
                refresh_clients()

        tree.bind("<Double-1>", lambda e: edit_selected())

        btn_frame = tk.Frame(frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Jauns klients", command=lambda: open_client_form(),
                   style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Rediģēt", command=edit_selected,
                   style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Dzēst", command=delete_selected,
                   style="Action.TButton").pack(side=tk.LEFT)

        refresh_clients()

    # =========================================================================
    # NEW DOCUMENT
    # =========================================================================
    def show_new_document(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Jauns dokuments", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        # Document type and client selection
        top_frame = tk.Frame(frame, bg="#f0f0f0")
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # Doc type
        tk.Label(top_frame, text="Veids:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=0, column=0, sticky="w", padx=(0, 10))
        doc_type_var = tk.StringVar(value="buy")
        type_frame = tk.Frame(top_frame, bg="#f0f0f0")
        type_frame.grid(row=0, column=1, sticky="w", padx=(0, 30))
        tk.Radiobutton(type_frame, text="Pirkums", variable=doc_type_var, value="buy",
                       font=FONT_MEDIUM, bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 15))
        tk.Radiobutton(type_frame, text="Pārdošana", variable=doc_type_var, value="sell",
                       font=FONT_MEDIUM, bg="#f0f0f0").pack(side=tk.LEFT)

        # Client
        tk.Label(top_frame, text="Klients:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        clients = db.get_all_clients()
        client_names = [c["name"] for c in clients]
        client_ids = [c["id"] for c in clients]
        client_var = tk.StringVar()
        client_frame = tk.Frame(top_frame, bg="#f0f0f0")
        client_frame.grid(row=1, column=1, sticky="w", pady=5)
        client_combo = ttk.Combobox(client_frame, textvariable=client_var,
                                     values=client_names, font=FONT_MEDIUM,
                                     width=35, state="readonly")
        client_combo.pack(side=tk.LEFT, padx=(0, 5))

        def quick_add_client():
            dialog = tk.Toplevel(self)
            dialog.title("Jauns klients")
            dialog.geometry("500x450")
            dialog.transient(self)
            dialog.grab_set()
            dialog.configure(bg="#f0f0f0")

            fields = [
                ("name", "Nosaukums *"),
                ("reg_number", "Reģistrācijas Nr."),
                ("vat_number", "PVN Nr."),
                ("legal_address", "Juridiskā adrese"),
                ("bank_name", "Banka"),
                ("bank_account", "Bankas konts"),
                ("contact_person", "Kontaktpersona"),
                ("phone", "Tālrunis"),
                ("email", "E-pasts"),
            ]

            entries = {}
            form = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=15)
            form.pack(fill=tk.BOTH, expand=True)

            for i, (key, label) in enumerate(fields):
                tk.Label(form, text=label + ":", font=FONT_MEDIUM,
                         bg="#f0f0f0").grid(row=i, column=0, sticky="w", pady=3, padx=(0, 10))
                entry = tk.Entry(form, font=FONT_MEDIUM, width=35)
                entry.grid(row=i, column=1, sticky="ew", pady=3)
                entries[key] = entry
            form.columnconfigure(1, weight=1)

            def save():
                name = entries["name"].get().strip()
                if not name:
                    messagebox.showwarning("Kļūda", "Ievadiet klienta nosaukumu!", parent=dialog)
                    return
                kwargs = {k: e.get().strip() for k, e in entries.items()}
                new_id = db.add_client(**kwargs)
                dialog.destroy()
                # Refresh client list and select the new one
                new_clients = db.get_all_clients()
                client_names.clear()
                client_ids.clear()
                for c in new_clients:
                    client_names.append(c["name"])
                    client_ids.append(c["id"])
                client_combo['values'] = client_names
                client_var.set(name)

            btn_frame = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=10)
            btn_frame.pack(fill=tk.X)
            ttk.Button(btn_frame, text="Saglabāt", command=save,
                       style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="Atcelt", command=dialog.destroy,
                       style="Action.TButton").pack(side=tk.LEFT)

        ttk.Button(client_frame, text="+ Jauns", command=quick_add_client,
                   style="Action.TButton").pack(side=tk.LEFT)

        # Date
        tk.Label(top_frame, text="Datums:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        date_entry = tk.Entry(top_frame, font=FONT_MEDIUM, width=15)
        date_entry.grid(row=2, column=1, sticky="w", pady=5)
        date_entry.insert(0, datetime.date.today().strftime("%d.%m.%Y"))

        # Notes
        tk.Label(top_frame, text="Piezīmes:", font=FONT_MEDIUM, bg="#f0f0f0").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=5)
        notes_entry = tk.Entry(top_frame, font=FONT_MEDIUM, width=40)
        notes_entry.grid(row=3, column=1, sticky="w", pady=5)

        # Line items section
        items_frame = tk.LabelFrame(frame, text="Preces", font=FONT_MEDIUM,
                                     bg="#f0f0f0", padx=15, pady=10)
        items_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Add item row
        add_row = tk.Frame(items_frame, bg="#f0f0f0")
        add_row.pack(fill=tk.X, pady=(0, 10))

        products = db.get_all_products()
        product_display_names = [f"{p['name']} ({p['unit']})" for p in products]
        product_map = {f"{p['name']} ({p['unit']})": p for p in products}

        tk.Label(add_row, text="Produkts:", font=FONT_SMALL, bg="#f0f0f0").grid(
            row=0, column=0, sticky="w", padx=(0, 5))
        prod_var = tk.StringVar()
        prod_combo = ttk.Combobox(add_row, textvariable=prod_var, values=product_display_names,
                                   font=FONT_SMALL, width=25, state="readonly")
        prod_combo.grid(row=0, column=1, padx=(0, 3))

        def refresh_product_list():
            """Refresh the product dropdown after adding a new product."""
            new_products = db.get_all_products()
            product_display_names.clear()
            product_map.clear()
            for p in new_products:
                dn = f"{p['name']} ({p['unit']})"
                product_display_names.append(dn)
                product_map[dn] = p
            prod_combo['values'] = product_display_names

        def quick_add_product():
            dialog = tk.Toplevel(self)
            dialog.title("Jauns produkts")
            dialog.geometry("400x200")
            dialog.transient(self)
            dialog.grab_set()
            dialog.configure(bg="#f0f0f0")

            form = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=15)
            form.pack(fill=tk.BOTH, expand=True)

            tk.Label(form, text="Nosaukums:", font=FONT_MEDIUM,
                     bg="#f0f0f0").grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
            name_entry = tk.Entry(form, font=FONT_MEDIUM, width=25)
            name_entry.grid(row=0, column=1, sticky="ew", pady=5)

            tk.Label(form, text="Mērvienība:", font=FONT_MEDIUM,
                     bg="#f0f0f0").grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
            unit_var_dlg = tk.StringVar(value=UNITS[0])
            unit_combo_dlg = ttk.Combobox(form, textvariable=unit_var_dlg, values=UNITS,
                                          font=FONT_MEDIUM, width=10, state="readonly")
            unit_combo_dlg.grid(row=1, column=1, sticky="w", pady=5)
            form.columnconfigure(1, weight=1)

            def save():
                name = name_entry.get().strip()
                if not name:
                    messagebox.showwarning("Kļūda", "Ievadiet produkta nosaukumu!", parent=dialog)
                    return
                db.add_product(name, unit_var_dlg.get())
                dialog.destroy()
                refresh_product_list()
                # Select the newly added product
                new_display = f"{name} ({unit_var_dlg.get()})"
                if new_display in product_map:
                    prod_var.set(new_display)
                    on_product_select()

            btn_frame = tk.Frame(dialog, bg="#f0f0f0", padx=20, pady=10)
            btn_frame.pack(fill=tk.X)
            ttk.Button(btn_frame, text="Saglabāt", command=save,
                       style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="Atcelt", command=dialog.destroy,
                       style="Action.TButton").pack(side=tk.LEFT)

        ttk.Button(add_row, text="+ Jauns", command=quick_add_product,
                   style="Action.TButton").grid(row=0, column=2, padx=(0, 10))

        tk.Label(add_row, text="Daudzums:", font=FONT_SMALL, bg="#f0f0f0").grid(
            row=0, column=3, sticky="w", padx=(0, 5))
        qty_entry = tk.Entry(add_row, font=FONT_SMALL, width=10)
        qty_entry.grid(row=0, column=4, padx=(0, 10))

        tk.Label(add_row, text="Cena:", font=FONT_SMALL, bg="#f0f0f0").grid(
            row=0, column=5, sticky="w", padx=(0, 5))
        price_entry = tk.Entry(add_row, font=FONT_SMALL, width=10)
        price_entry.grid(row=0, column=6, padx=(0, 5))

        # VAT toggle for price input
        default_vat_incl = db.get_setting("default_price_includes_vat", "0") == "1"
        price_vat_var = tk.StringVar(value="1" if default_vat_incl else "0")
        vat_toggle_frame = tk.Frame(add_row, bg="#f0f0f0")
        vat_toggle_frame.grid(row=0, column=7, padx=(0, 10))
        tk.Radiobutton(vat_toggle_frame, text="bez PVN", variable=price_vat_var, value="0",
                       font=("Segoe UI", 9), bg="#f0f0f0").pack(side=tk.LEFT)
        tk.Radiobutton(vat_toggle_frame, text="ar PVN", variable=price_vat_var, value="1",
                       font=("Segoe UI", 9), bg="#f0f0f0").pack(side=tk.LEFT)

        unit_label = tk.Label(add_row, text="", font=FONT_SMALL, bg="#f0f0f0")
        unit_label.grid(row=0, column=8, padx=(0, 10))

        stock_info_label = tk.Label(items_frame, text="", font=FONT_MEDIUM, bg="#f0f0f0", fg="#2c3e50")
        stock_info_label.pack(anchor="w", pady=(0, 5))

        def on_product_select(event=None):
            display_name = prod_var.get()
            if display_name in product_map:
                product = product_map[display_name]
                unit_label.config(text=product["unit"])
                stock = db.get_product_stock(product["id"])
                # Subtract already-added items
                already_added = sum(
                    it["quantity"] for it in line_items
                    if it["product_id"] == product["id"]
                )
                available = stock - already_added
                stock_info_label.config(
                    text=f"Noliktavā: {available:.2f} {product['unit']}",
                    fg="green" if available > 0 else "red"
                )

        prod_combo.bind("<<ComboboxSelected>>", on_product_select)

        # Items list
        items_tree = ttk.Treeview(items_frame,
                                   columns=("product", "qty", "unit", "price_no_vat", "price_with_vat", "total_no_vat"),
                                   show="headings", height=8)
        items_tree.heading("product", text="Produkts")
        items_tree.heading("qty", text="Daudzums")
        items_tree.heading("unit", text="Mērvienība")
        items_tree.heading("price_no_vat", text="Cena (bez PVN)")
        items_tree.heading("price_with_vat", text="Cena (ar PVN)")
        items_tree.heading("total_no_vat", text="Summa (bez PVN)")
        items_tree.column("product", width=170)
        items_tree.column("qty", width=80)
        items_tree.column("unit", width=70)
        items_tree.column("price_no_vat", width=110)
        items_tree.column("price_with_vat", width=110)
        items_tree.column("total_no_vat", width=110)

        # Store items data
        line_items = []

        total_label = tk.Label(items_frame, text="Kopā: 0.00 EUR", font=FONT_LARGE,
                               bg="#f0f0f0", anchor="e")

        def refresh_items_tree():
            items_tree.delete(*items_tree.get_children())
            grand_total_no_vat = 0
            vat_rate = float(db.get_setting("default_vat_rate", "21"))
            for i, item in enumerate(line_items):
                price_input = item["price_per_unit"]
                includes_vat = item.get("price_includes_vat", False)
                if includes_vat:
                    p_with = price_input
                    p_no = round(price_input / (1 + vat_rate / 100), 4)
                else:
                    p_no = price_input
                    p_with = round(price_input * (1 + vat_rate / 100), 4)
                total_no = round(item["quantity"] * p_no, 2)
                grand_total_no_vat += total_no
                tag = "evenrow" if i % 2 else "oddrow"
                items_tree.insert("", tk.END, values=(
                    item["product_name"], f"{item['quantity']:.2f}",
                    item["unit"], f"{p_no:.2f}", f"{p_with:.2f}", f"{total_no:.2f}"
                ), tags=(tag,))
            vat_amount = round(grand_total_no_vat * (vat_rate / 100), 2)
            grand_total = grand_total_no_vat + vat_amount
            total_label.config(text=f"Bez PVN: {grand_total_no_vat:.2f}  |  PVN: {vat_amount:.2f}  |  Kopā: {grand_total:.2f} EUR")

        def add_item():
            display_name = prod_var.get()
            if not display_name or display_name not in product_map:
                messagebox.showwarning("Kļūda", "Izvēlieties produktu!")
                return
            try:
                qty = float(qty_entry.get())
                price = float(price_entry.get())
            except ValueError:
                messagebox.showwarning("Kļūda", "Ievadiet derīgu daudzumu un cenu!")
                return

            if qty <= 0 or price <= 0:
                messagebox.showwarning("Kļūda", "Daudzumam un cenai jābūt lielākai par 0!")
                return

            product = product_map[display_name]

            # Check stock for sell
            if doc_type_var.get() == "sell":
                available = db.get_product_stock(product["id"])
                # Also subtract any already-added items for this product
                already_added = sum(
                    it["quantity"] for it in line_items
                    if it["product_id"] == product["id"]
                )
                if qty > available - already_added:
                    messagebox.showwarning(
                        "Nepietiekams daudzums",
                        f"{product['name']}: pieejams {available - already_added:.2f} {product['unit']}, "
                        f"pieprasīts {qty:.2f} {product['unit']}"
                    )
                    return

            line_items.append({
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": qty,
                "unit": product["unit"],
                "price_per_unit": price,
                "price_includes_vat": price_vat_var.get() == "1",
            })

            # Clear inputs
            prod_combo.set("")
            qty_entry.delete(0, tk.END)
            price_entry.delete(0, tk.END)
            unit_label.config(text="")
            stock_info_label.config(text="")
            refresh_items_tree()

        def remove_item():
            sel = items_tree.selection()
            if not sel:
                return
            idx = items_tree.index(sel[0])
            line_items.pop(idx)
            refresh_items_tree()

        ttk.Button(add_row, text="Pievienot", command=add_item,
                   style="Action.TButton").grid(row=0, column=9)

        items_tree.pack(fill=tk.BOTH, expand=True)
        self.style_treeview(items_tree)
        total_label.pack(fill=tk.X, pady=(5, 0))

        # Bottom buttons
        bottom_frame = tk.Frame(frame, bg="#f0f0f0")
        bottom_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(bottom_frame, text="Noņemt izvēlēto", command=remove_item,
                   style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))

        def save_document():
            if not client_var.get():
                messagebox.showwarning("Kļūda", "Izvēlieties klientu!")
                return
            if not line_items:
                messagebox.showwarning("Kļūda", "Pievienojiet vismaz vienu preci!")
                return

            try:
                date_str = date_entry.get().strip()
                doc_date = datetime.datetime.strptime(date_str, "%d.%m.%Y").date()
            except ValueError:
                messagebox.showwarning("Kļūda", "Nederīgs datuma formāts! Izmantojiet DD.MM.GGGG")
                return

            client_idx = client_names.index(client_var.get())
            client_id = client_ids[client_idx]
            doc_type = doc_type_var.get()
            vat_rate = float(db.get_setting("default_vat_rate", "21"))

            try:
                doc_id, doc_number = db.create_document(
                    doc_type=doc_type,
                    client_id=client_id,
                    doc_date=doc_date,
                    items=line_items,
                    vat_rate=vat_rate,
                    notes=notes_entry.get().strip()
                )
            except ValueError as e:
                messagebox.showerror("Kļūda", str(e))
                return

            result = messagebox.askyesno(
                "Dokuments izveidots",
                f"Dokuments {doc_number} izveidots!\n\nVai ģenerēt PDF?"
            )

            if result:
                try:
                    from pdf_generator import generate_invoice_pdf
                    filepath = generate_invoice_pdf(doc_id)
                    # Try to open the PDF
                    if sys.platform == "win32":
                        os.startfile(filepath)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", filepath])
                    else:
                        subprocess.run(["xdg-open", filepath])
                except Exception as e:
                    messagebox.showerror("Kļūda", f"PDF kļūda: {e}")

            # Reset form
            line_items.clear()
            refresh_items_tree()
            client_combo.set("")
            notes_entry.delete(0, tk.END)
            date_entry.delete(0, tk.END)
            date_entry.insert(0, datetime.date.today().strftime("%d.%m.%Y"))

        ttk.Button(bottom_frame, text="Saglabāt dokumentu", command=save_document,
                   style="Action.TButton").pack(side=tk.RIGHT)

    # =========================================================================
    # DOCUMENTS LIST
    # =========================================================================
    def show_documents(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Dokumenti", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        # Filter row
        filter_frame = tk.Frame(frame, bg="#f0f0f0")
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(filter_frame, text="Veids:", font=FONT_SMALL, bg="#f0f0f0").pack(
            side=tk.LEFT, padx=(0, 5))
        filter_type = tk.StringVar(value="")
        filter_display_map = {"": "", "Iegāde": "buy", "Pārdošana": "sell"}
        type_combo = ttk.Combobox(filter_frame, textvariable=filter_type,
                                   values=["", "Iegāde", "Pārdošana"], font=FONT_SMALL,
                                   width=14, state="readonly")
        type_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Documents tree
        tree_frame = tk.Frame(frame, bg="#f0f0f0")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame,
                            columns=("id", "number", "type", "client", "date", "total"),
                            show="headings", height=15)
        tree.heading("id", text="ID")
        tree.heading("number", text="Numurs")
        tree.heading("type", text="Veids")
        tree.heading("client", text="Klients")
        tree.heading("date", text="Datums")
        tree.heading("total", text="Summa")
        tree.column("id", width=40)
        tree.column("number", width=150)
        tree.column("type", width=100)
        tree.column("client", width=200)
        tree.column("date", width=100)
        tree.column("total", width=100)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.style_treeview(tree)

        def refresh_docs():
            tree.delete(*tree.get_children())
            doc_type = filter_display_map.get(filter_type.get(), None) or None
            docs = db.get_documents(doc_type=doc_type)
            for i, d in enumerate(docs):
                # Calculate total
                _, items = db.get_document(d["id"])
                total = sum(it["quantity"] * it["price_per_unit"] for it in items)
                type_label = "Pirkums" if d["doc_type"] == "buy" else "Pārdošana"
                # Format date
                try:
                    dd = datetime.datetime.strptime(d["doc_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
                except Exception:
                    dd = d["doc_date"]
                tag = "evenrow" if i % 2 else "oddrow"
                tree.insert("", tk.END, values=(
                    d["id"], d["doc_number"], type_label,
                    d["client_name"], dd, f"{total:.2f}"
                ), tags=(tag,))

        type_combo.bind("<<ComboboxSelected>>", lambda e: refresh_docs())

        def open_pdf():
            sel = tree.selection()
            if not sel:
                return
            doc_id = tree.item(sel[0])["values"][0]
            try:
                from pdf_generator import generate_invoice_pdf
                filepath = generate_invoice_pdf(doc_id)
                if sys.platform == "win32":
                    os.startfile(filepath)
                elif sys.platform == "darwin":
                    subprocess.run(["open", filepath])
                else:
                    subprocess.run(["xdg-open", filepath])
            except Exception as e:
                messagebox.showerror("Kļūda", f"PDF kļūda: {e}")

        def delete_doc():
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])["values"]
            if messagebox.askyesno("Dzēst?", f"Vai tiešām dzēst dokumentu {vals[1]}?\n"
                                              "Noliktavas atlikumi tiks koriģēti."):
                db.delete_document(vals[0])
                refresh_docs()

        btn_frame = tk.Frame(frame, bg="#f0f0f0")
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Atvērt PDF", command=open_pdf,
                   style="Action.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Dzēst", command=delete_doc,
                   style="Action.TButton").pack(side=tk.LEFT)

        refresh_docs()

    # =========================================================================
    # STOCK
    # =========================================================================
    def show_stock(self):
        scrollable = self.clear_content()
        frame = tk.Frame(scrollable, bg="#f0f0f0", padx=30, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Noliktavas atlikumi", font=FONT_LARGE,
                 bg="#f0f0f0").pack(anchor="w", pady=(0, 15))

        # Month filter
        filter_frame = tk.Frame(frame, bg="#f0f0f0")
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(filter_frame, text="Mēnesis:", font=FONT_MEDIUM, bg="#f0f0f0").pack(
            side=tk.LEFT, padx=(0, 5))

        now = datetime.date.today()
        months_lv = ["Janvāris", "Februāris", "Marts", "Aprīlis", "Maijs", "Jūnijs",
                     "Jūlijs", "Augusts", "Septembris", "Oktobris", "Novembris", "Decembris"]

        # Build month options: current year months + "Visi"
        month_options = ["Visi"]
        month_data = [None]  # None = no filter
        for m in range(1, 13):
            label = f"{months_lv[m-1]} {now.year}"
            month_options.append(label)
            month_data.append((now.year, m))

        month_var = tk.StringVar(value=month_options[now.month])  # Default to current month
        month_combo = ttk.Combobox(filter_frame, textvariable=month_var,
                                    values=month_options, font=FONT_MEDIUM,
                                    width=20, state="readonly")
        month_combo.pack(side=tk.LEFT, padx=(0, 15))

        tree_frame = tk.Frame(frame, bg="#f0f0f0")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame,
                            columns=("name", "bought", "sold", "stock", "unit"),
                            show="headings", height=15)
        tree.heading("name", text="Produkts")
        tree.heading("bought", text="Nopirkts")
        tree.heading("sold", text="Pārdots")
        tree.heading("stock", text="Atlikums")
        tree.heading("unit", text="Mērvienība")
        tree.column("name", width=200)
        tree.column("bought", width=100)
        tree.column("sold", width=100)
        tree.column("stock", width=100)
        tree.column("unit", width=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.style_treeview(tree)

        tree.tag_configure("zero", foreground="gray")
        tree.tag_configure("positive", foreground="green")
        tree.tag_configure("negative", foreground="red")

        def refresh_stock(*args):
            tree.delete(*tree.get_children())
            idx = month_options.index(month_var.get()) if month_var.get() in month_options else 0
            md = month_data[idx]

            if md:
                year, month = md
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                date_from = f"{year}-{month:02d}-01"
                date_to = f"{year}-{month:02d}-{last_day:02d}"
                stock = db.get_stock(date_from=date_from, date_to=date_to)
            else:
                stock = db.get_stock()

            for i, s in enumerate(stock):
                if s["stock"] > 0:
                    color_tag = "positive" if i % 2 == 0 else "positive_even"
                elif s["stock"] < 0:
                    color_tag = "negative" if i % 2 == 0 else "negative_even"
                else:
                    color_tag = "zero" if i % 2 == 0 else "zero_even"
                row_tag = "oddrow" if i % 2 == 0 else "evenrow"
                tree.insert("", tk.END, values=(
                    s["name"], f"{s['bought']:.2f}", f"{s['sold']:.2f}",
                    f"{s['stock']:.2f}", s["unit"]
                ), tags=(color_tag, row_tag))

        month_combo.bind("<<ComboboxSelected>>", refresh_stock)
        refresh_stock()


if __name__ == "__main__":
    app = App()
    app.mainloop()
