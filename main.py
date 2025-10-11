# main.py — Login en la raíz + Menú con "Usuarios" y "OCR"
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import threading
import queue
import json
import os
import importlib.util

from services.auth_service import check_password, hash_password
from db.db_connector import (
    check_login,
    list_users, create_user, update_user, reset_password,
    save_ocr_record
)

SESSION = {'user_id': None, 'rol': None, 'username': None}

# =============== Utilidad para importar tus módulos ocr_text_only.py y app8.py ===============
def _import_module_from_path(py_path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, py_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {module_name} desde {py_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ==========================================================
#  Panel de Administración de Usuarios (CRUD)
# ==========================================================
class UserAdminFrame(tk.Frame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        tk.Label(self, text="Administración de Usuarios", font=("Arial", 14, "bold")).pack(pady=10)

        cols = ("id","username","rol","activo","nombre")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, txt in zip(cols, ["ID","Usuario","Rol","Activo","Nombre completo"]):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=120 if c!="nombre" else 220, anchor=tk.CENTER if c!="nombre" else tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        form = tk.Frame(self); form.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(form, text="Usuario").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        tk.Label(form, text="Nombre").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        tk.Label(form, text="Rol").grid(row=0, column=2, sticky="e", padx=5, pady=4)
        tk.Label(form, text="Activo").grid(row=1, column=2, sticky="e", padx=5, pady=4)
        tk.Label(form, text="Nueva Clave (opcional)").grid(row=2, column=0, sticky="e", padx=5, pady=4)

        self.e_user = tk.Entry(form, width=24)
        self.e_nombre = tk.Entry(form, width=36)
        self.cb_rol = ttk.Combobox(form, values=["administrador","consultor"], state="readonly", width=18)
        self.var_activo = tk.BooleanVar(value=True)
        self.cb_activo = ttk.Checkbutton(form, variable=self.var_activo)
        self.e_pwd = tk.Entry(form, width=24, show="*")

        self.e_user.grid(row=0, column=1, sticky="w", padx=5)
        self.e_nombre.grid(row=1, column=1, sticky="w", padx=5)
        self.cb_rol.grid(row=0, column=3, sticky="w", padx=5)
        self.cb_activo.grid(row=1, column=3, sticky="w", padx=5)
        self.e_pwd.grid(row=2, column=1, sticky="w", padx=5)

        btns = tk.Frame(self); btns.pack(fill=tk.X, padx=10, pady=(0,10))
        tk.Button(btns, text="Nuevo", command=self.do_new).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Guardar (Crear/Actualizar)", command=self.do_save).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Resetear Contraseña", command=self.do_reset_pwd).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Inactivar", command=self.do_inactivate).pack(side=tk.LEFT, padx=4)
        tk.Button(btns, text="Refrescar", command=self.refresh).pack(side=tk.RIGHT, padx=4)

        self.selected_id = None
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        rows = list_users()
        for r in rows:
            self.tree.insert("", tk.END, values=(r["id"], r["username"], r["rol"], "Sí" if r["activo"] else "No", r["nombre_completo"]))
        self.selected_id = None

    def on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.selected_id = int(vals[0])
        self.e_user.delete(0, tk.END); self.e_user.insert(0, vals[1])
        self.cb_rol.set(vals[2])
        self.var_activo.set(vals[3] == "Sí")
        self.e_nombre.delete(0, tk.END); self.e_nombre.insert(0, vals[4])
        self.e_pwd.delete(0, tk.END)

    def do_new(self):
        self.selected_id = None
        self.e_user.delete(0, tk.END)
        self.e_nombre.delete(0, tk.END)
        self.cb_rol.set("consultor")
        self.var_activo.set(True)
        self.e_pwd.delete(0, tk.END)
        self.e_user.focus_set()

    def do_save(self):
        username = (self.e_user.get() or "").strip()
        nombre = (self.e_nombre.get() or "").strip()
        rol = self.cb_rol.get() or "consultor"
        activo = bool(self.var_activo.get())
        pwd = (self.e_pwd.get() or "").strip()

        if not username:
            messagebox.showerror("Validación", "El campo Usuario es obligatorio.")
            return
        if self.selected_id is None:
            if not pwd:
                messagebox.showerror("Validación", "Para crear un usuario, ingrese la contraseña.")
                return
            try:
                h = hash_password(pwd)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo hashear la contraseña: {e}")
                return
            new_id = create_user(username, h, rol=rol, nombre_completo=nombre, activo=activo)
            if new_id:
                messagebox.showinfo("OK", f"Usuario creado (id={new_id}).")
                self.refresh()
            else:
                messagebox.showerror("Error", "No se pudo crear el usuario (¿username duplicado?).")
        else:
            ok = update_user(self.selected_id, rol=rol, nombre_completo=nombre, activo=activo)
            if ok:
                messagebox.showinfo("OK", "Usuario actualizado.")
                self.refresh()
            else:
                messagebox.showerror("Error", "No se pudo actualizar el usuario.")

    def do_reset_pwd(self):
        if self.selected_id is None:
            messagebox.showwarning("Atención", "Seleccione un usuario de la lista.")
            return
        pwd = (self.e_pwd.get() or "").strip()
        if not pwd:
            messagebox.showerror("Validación", "Ingrese la nueva contraseña en el campo 'Nueva Clave'.")
            return
        try:
            h = hash_password(pwd)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo hashear la contraseña: {e}")
            return
        ok = reset_password(self.selected_id, h)
        if ok:
            messagebox.showinfo("OK", "Contraseña reseteada.")
            self.e_pwd.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "No se pudo resetear la contraseña.")

    def do_inactivate(self):
        if self.selected_id is None:
            messagebox.showwarning("Atención", "Seleccione un usuario de la lista.")
            return
        if not messagebox.askyesno("Confirmar", "¿Inactivar este usuario?"):
            return
        ok = update_user(self.selected_id, activo=False)
        if ok:
            messagebox.showinfo("OK", "Usuario inactivado.")
            self.refresh()
        else:
            messagebox.showerror("Error", "No se pudo inactivar el usuario.")

# ==========================================================
#  Panel OCR (múltiples archivos, tabla editable, guardar en BD)
# ==========================================================
class OCRFrame(tk.Frame):
    COLS = ['Nombres','Apellidos','DNI','Fecha de Nacimiento','Libro','Folio','Clase',
            'Unidad de alta','Fecha de alta','Unidad de Baja','Fecha de baja','Grado','__source']

    def __init__(self, master, ocr_path="ocr_text_only.py", parser_path="app8.py", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.ocr_path = ocr_path
        self.parser_path = parser_path
        self.queue = queue.Queue()
        self.worker = None
        self.records = []  # lista de dicts (una fila por archivo)
        self._editing = None  # (item_id, column)

        tk.Label(self, text="OCR de Documentos (PDF/Imagen)", font=("Arial", 14, "bold")).pack(pady=10)

        # Botonera
        top = tk.Frame(self); top.pack(fill=tk.X, padx=10)
        tk.Button(top, text="Seleccionar archivos…", command=self.pick_files).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Procesar OCR", command=self.start_ocr).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Guardar fila", command=self.save_selected).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="Guardar todas", command=self.save_all).pack(side=tk.LEFT, padx=4)

        # Barra de estado
        self.status = tk.Label(self, text="Listo.", anchor="w")
        self.status.pack(fill=tk.X, padx=10, pady=(4,6))

        # Tabla
        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings", height=14)
        for c in self.COLS:
            header = c if c != "__source" else "Archivo"
            self.tree.heading(c, text=header)
            width = 160 if c in ("Nombres","Apellidos","Unidad de alta","Unidad de Baja") else 120
            if c == "__source": width = 200
            self.tree.column(c, width=width, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,8))

        # Scroll
        ybar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=ybar.set)
        ybar.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # Editar celda con doble clic
        self.tree.bind("<Double-1>", self._begin_edit_cell)

        self.files = []  # paths seleccionados

    # ---------- UI helpers ----------
    def set_status(self, msg): 
        self.status.config(text=msg); self.update_idletasks()

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar PDFs/Imágenes",
            filetypes=[("PDF/Imagen", "*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff"), ("Todos", "*.*")]
        )
        if not paths: return
        self.files = list(paths)
        self.set_status(f"{len(self.files)} archivo(s) seleccionado(s).")

    def start_ocr(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("OCR", "Ya hay un proceso en ejecución.")
            return
        if not self.files:
            messagebox.showwarning("OCR", "Primero selecciona uno o más archivos.")
            return
        # limpia tabla
        self.tree.delete(*self.tree.get_children())
        self.records = []
        # Lanza hilo
        self.worker = threading.Thread(target=self._run_ocr_worker, daemon=True)
        self.worker.start()
        self.after(200, self._poll_queue)

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "progress":
                    self.set_status(payload)
                elif kind == "record":
                    rec = payload
                    self.records.append(rec)
                    values = [rec.get(k, "") for k in self.COLS]
                    self.tree.insert("", tk.END, values=values)
                elif kind == "done":
                    self.set_status("OCR completado.")
                elif kind == "error":
                    messagebox.showerror("OCR", payload)
        except queue.Empty:
            pass
        if self.worker and self.worker.is_alive():
            self.after(200, self._poll_queue)

    def _run_ocr_worker(self):
        try:
            # importa módulos
            ocr_mod = _import_module_from_path(self.ocr_path, "ocr_text_only")
            parser_mod = _import_module_from_path(self.parser_path, "app8")

            for i, path in enumerate(self.files, start=1):
                self.queue.put(("progress", f"Procesando {i}/{len(self.files)}: {os.path.basename(path)}"))
                # 1) Ejecutar OCR -> texto (reutilizamos funciones del módulo)
                #    Como tu script principal escribe archivos, aquí tomamos un camino directo:
                #    Convertimos páginas y procesamos como en tu main() pero por archivo único.
                #    Para no duplicar todo, usamos su 'convert_from_path' + preprocess_fast/quality
                from pdf2image import convert_from_path
                from PIL import Image
                import numpy as np
                import cv2, pytesseract
                from deskew import determine_skew

                def to_cv2(pil_img: Image.Image) -> np.ndarray:
                    return cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)

                def rotate_by_angle(img, angle):
                    if abs(angle) < 0.8:
                        return img
                    h, w = img.shape[:2]
                    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
                    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

                FAST_MODE = True  # igual que tu script por defecto
                dpi = 300 if FAST_MODE else 400
                pages_text = []
                cfg = '-l spa+eng --oem 1 --psm 6'

                def preprocess_fast(img_bgr):
                    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                    angle = determine_skew(gray)
                    img_bgr = rotate_by_angle(img_bgr, angle)
                    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
                    return bin_img

                ext = os.path.splitext(path.lower())[1]
                if ext == ".pdf":
                    pages = convert_from_path(path, dpi=dpi)
                    for p in pages:
                        bin_img = preprocess_fast(to_cv2(p))
                        txt = pytesseract.image_to_string(bin_img, config=cfg)
                        pages_text.append(txt.strip())
                else:
                    # imagen directa
                    img = Image.open(path)
                    bin_img = preprocess_fast(to_cv2(img))
                    txt = pytesseract.image_to_string(bin_img, config=cfg)
                    pages_text.append(txt.strip())

                full_text = "\n\n".join(pages_text)

                # 2) Parsear usando tu parser (app8.parse_text)
                data = parser_mod.parse_text(full_text)
                data["__source"] = path  # para mostrar el origen

                # 3) Enviar a la tabla
                self.queue.put(("record", data))

            self.queue.put(("done", None))
        except Exception as e:
            self.queue.put(("error", f"Error en OCR: {e}"))

    # ----------- edición de celdas ----------
    def _begin_edit_cell(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        col_index = int(col_id[1:]) - 1
        if col_index < 0 or col_index >= len(self.COLS):
            return
        col_name = self.COLS[col_index]
        if col_name == "__source":
            return  # no editable
        x, y, w, h = self.tree.bbox(item_id, col_id)
        value = self.tree.set(item_id, col_name)

        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, value)
        entry.focus_set()
        entry.select_range(0, tk.END)

        def finish_edit(_evt=None):
            new_val = entry.get()
            entry.destroy()
            self.tree.set(item_id, col_name, new_val)
            # también en self.records
            idx = self._tree_index(item_id)
            if idx is not None:
                self.records[idx][col_name] = new_val

        entry.bind("<Return>", finish_edit)
        entry.bind("<Escape>", lambda _e: entry.destroy())

    def _tree_index(self, item_id):
        # devuelve índice de item_id en la tabla
        items = self.tree.get_children()
        for i, it in enumerate(items):
            if it == item_id:
                return i
        return None

    # ---------- guardado ----------
    def _record_from_item(self, item_id):
        vals = self.tree.item(item_id, "values")
        rec = {k: vals[i] for i, k in enumerate(self.COLS)}
        return rec

    def save_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Guardar", "Seleccione una fila.")
            return
        ok_all = True
        for it in sel:
            rec = self._record_from_item(it)
            if not rec.get("DNI"):
                messagebox.showerror("Validación", "DNI es obligatorio para guardar.")
                ok_all = False; continue
            ok = save_ocr_record(rec, rec.get("__source","") or "")
            if not ok:
                ok_all = False
        if ok_all:
            messagebox.showinfo("Guardar", "Fila(s) guardada(s) correctamente.")
        else:
            messagebox.showwarning("Guardar", "Algunas filas no se pudieron guardar. Revise consola.")

    def save_all(self):
        if not self.tree.get_children():
            messagebox.showinfo("Guardar", "No hay filas para guardar.")
            return
        if not messagebox.askyesno("Confirmar", "¿Guardar todas las filas en la base de datos?"):
            return
        ok_all = True
        for it in self.tree.get_children():
            rec = self._record_from_item(it)
            if not rec.get("DNI"):
                ok_all = False; continue
            ok = save_ocr_record(rec, rec.get("__source","") or "")
            if not ok:
                ok_all = False
        if ok_all:
            messagebox.showinfo("Guardar", "Todos los registros guardados correctamente.")
        else:
            messagebox.showwarning("Guardar", "Algunos registros fallaron. Revise consola.")

# ==========================================================
#  Login + estructura principal con MENÚ
# ==========================================================
def attempt_login():
    username = user.get().strip()
    password = pwd.get()
    if not username or not password:
        messagebox.showerror("Error de Login", "Debe ingresar usuario y contraseña.")
        return

    row = check_login(username)  # (id, hash, rol) o None
    if not row:
        messagebox.showerror("Error de conexión",
            "No fue posible validar las credenciales.\nRevise consola y .env/DB.")
        return

    uid, h, rol = row
    ok = bool(h) and check_password(password, h)
    if ok:
        SESSION.update({'user_id': uid, 'rol': rol, 'username': username})
        messagebox.showinfo("Éxito", f"Bienvenido, {username} ({rol})")
        show_main()
    else:
        messagebox.showerror("Error de Login", "Usuario o contraseña incorrectos.")

def show_main():
    for w in root.winfo_children():
        w.destroy()
    root.title("Aplicación de Gestión Documental")

    # Menú superior
    menubar = tk.Menu(root)
    m_admin = tk.Menu(menubar, tearoff=0)
    m_proc  = tk.Menu(menubar, tearoff=0)
    m_help  = tk.Menu(menubar, tearoff=0)

    if (SESSION.get("rol") == "administrador"):
        m_admin.add_command(label="Usuarios…", command=lambda: mount_frame(UserAdminFrame))
    menubar.add_cascade(label="Administración", menu=m_admin)

    m_proc.add_command(label="OCR (PDF/Imagen)…", command=lambda: mount_frame(OCRFrame))
    menubar.add_cascade(label="Procesos", menu=m_proc)

    m_help.add_command(label="Acerca de", command=lambda: messagebox.showinfo("Acerca de", "Sistema de Gestión Documental - OCR"))
    menubar.add_cascade(label="Ayuda", menu=m_help)

    root.config(menu=menubar)

    # Bienvenida
    lbl = tk.Label(root, text=f"Bienvenido, {SESSION.get('username')} ({SESSION.get('rol')})",
                   font=("Arial", 14))
    lbl.pack(pady=18)

    # Contenedor central
    global content
    content = tk.Frame(root)
    content.pack(fill=tk.BOTH, expand=True)

    # Por defecto si admin, abre usuarios; si no, sólo mensaje
    if SESSION.get("rol") == "administrador":
        mount_frame(UserAdminFrame)

def mount_frame(frame_cls):
    for c in content.winfo_children():
        c.destroy()
    # Si montamos OCRFrame, le pasamos rutas a tus scripts en la raíz del proyecto
    if frame_cls is OCRFrame:
        frm = OCRFrame(content, ocr_path="ocr_text_only.py", parser_path="app8.py")
    else:
        frm = frame_cls(content)
    frm.pack(fill=tk.BOTH, expand=True)

# ============== App (login en raíz) ==============
root = tk.Tk()
root.title("Login")
root.geometry("480x260")
root.bind("<Escape>", lambda e: root.destroy())
root.bind("<Control-q>", lambda e: root.destroy())

tk.Label(root, text="Usuario").pack(pady=(12,4))
user = tk.Entry(root); user.pack()
tk.Label(root, text="Contraseña").pack(pady=(8,4))
pwd = tk.Entry(root, show="*"); pwd.pack()
tk.Button(root, text="Ingresar", command=attempt_login).pack(pady=12)

# Traer delante y enfocar
root.lift(); root.attributes('-topmost', True); root.after(400, lambda: root.attributes('-topmost', False))
user.focus_set()

root.mainloop()
