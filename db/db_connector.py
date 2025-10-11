# db/db_connector.py
import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# ===== Localizar .env aunque ejecutes desde subcarpetas =====
def _find_dotenv(start: Path):
    for p in [start, *start.parents]:
        env = p / ".env"
        if env.exists():
            return env
    return None

BASE_DIR = Path(__file__).resolve().parents[1]  # raíz del proyecto (donde está main.py)
ENV_PATH = _find_dotenv(Path(__file__).resolve()) or (BASE_DIR / ".env")
if ENV_PATH and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()  # fallback

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "connect_timeout": 5,
    # "sslmode": "require",  # descomenta si tu servidor lo exige
}

def get_connection():
    """Devuelve conexión psycopg2 o None (logeando el motivo)."""
    missing = [k for k in ("dbname", "user", "password") if not DB_CONFIG.get(k)]
    if missing:
        print(f"[DB] ERROR: faltan variables en .env: {', '.join(missing)}. .env usado: {ENV_PATH}")
        return None
    try:
        print(f"[DB] Conectando a {DB_CONFIG['host']}:{DB_CONFIG['port']} db={DB_CONFIG['dbname']} user={DB_CONFIG['user']}")
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"[DB] ERROR de conexión: {e}")
        return None

def check_login(username: str):
    """
    Devuelve (id, hash_password, rol) si encuentra usuario ACTIVO.
    Si no hay conexión o falla la query, devuelve None.
    """
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, hash_password, rol
                FROM usuarios
                WHERE username = %s AND activo = TRUE
                """,
                (username.strip(),)
            )
            row = cur.fetchone()
            if row:
                print(f"[DB] Usuario encontrado: id={row[0]}, rol={row[2]}")
            else:
                print("[DB] Usuario no encontrado o inactivo.")
            return row
    except Exception as e:
        print(f"[DB] ERROR en consulta check_login: {e}")
        return None
    finally:
        try: conn.close()
        except Exception: pass

# =========================
# CRUD USUARIOS (admin)
# =========================
def list_users():
    """
    Devuelve lista de dicts: [{'id':..,'username':..,'rol':..,'activo':..,'nombre_completo':..}, ...]
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, username, rol, activo, COALESCE(nombre_completo,'')
                FROM usuarios
                ORDER BY id ASC
            """)
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "username": r[1],
                    "rol": r[2],
                    "activo": r[3],
                    "nombre_completo": r[4],
                } for r in rows
            ]
    except Exception as e:
        print(f"[DB] ERROR list_users: {e}")
        return []
    finally:
        try: conn.close()
        except Exception: pass

def create_user(username: str, hashed_password: str, rol: str = "consultor", nombre_completo: str = "", activo: bool = True):
    """
    Crea usuario. Devuelve id o None.
    """
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO usuarios (username, hash_password, rol, activo, nombre_completo)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (username.strip(), hashed_password, rol, activo, nombre_completo.strip()))
            new_id = cur.fetchone()[0]
            conn.commit()
            print(f"[DB] Usuario creado id={new_id}")
            return new_id
    except Exception as e:
        print(f"[DB] ERROR create_user: {e}")
        return None
    finally:
        try: conn.close()
        except Exception: pass

def update_user(user_id: int, rol: str = None, nombre_completo: str = None, activo: bool = None):
    """
    Actualiza rol / nombre_completo / activo del usuario. Devuelve True/False.
    """
    if rol is None and nombre_completo is None and activo is None:
        return True
    conn = get_connection()
    if not conn:
        return False
    try:
        sets, vals = [], []
        if rol is not None:
            sets.append("rol=%s"); vals.append(rol)
        if nombre_completo is not None:
            sets.append("nombre_completo=%s"); vals.append(nombre_completo.strip())
        if activo is not None:
            sets.append("activo=%s"); vals.append(bool(activo))
        vals.append(user_id)

        q = f"UPDATE usuarios SET {', '.join(sets)} WHERE id=%s"
        with conn.cursor() as cur:
            cur.execute(q, tuple(vals))
            conn.commit()
            print(f"[DB] Usuario {user_id} actualizado.")
            return True
    except Exception as e:
        print(f"[DB] ERROR update_user: {e}")
        return False
    finally:
        try: conn.close()
        except Exception: pass

def reset_password(user_id: int, new_hashed_password: str):
    """
    Resetea contraseña. Devuelve True/False.
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE usuarios SET hash_password=%s WHERE id=%s
            """, (new_hashed_password, user_id))
            conn.commit()
            print(f"[DB] Password reseteado para user_id={user_id}")
            return True
    except Exception as e:
        print(f"[DB] ERROR reset_password: {e}")
        return False
    finally:
        try: conn.close()
        except Exception: pass

def delete_user(user_id: int):
    """
    Eliminación dura (opcional). Recomendado usar inactivación mejor.
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios WHERE id=%s", (user_id,))
            conn.commit()
            print(f"[DB] Usuario {user_id} eliminado.")
            return True
    except Exception as e:
        print(f"[DB] ERROR delete_user: {e}")
        return False
    finally:
        try: conn.close()
        except Exception: pass
# ==== Helpers de guardado OCR ====
def _get_or_create_ciudadano(conn, dni: str, apellidos: str, nombres: str, fecha_nac: str, clase: str):
    """Upsert básico de ciudadano por DNI. Devuelve id del ciudadano."""
    with conn.cursor() as cur:
        # intenta encontrar por DNI
        cur.execute("SELECT id FROM ciudadanos WHERE dni=%s", (dni,))
        r = cur.fetchone()
        if r:
            cid = r[0]
            # actualiza campos no vacíos
            cur.execute("""
                UPDATE ciudadanos
                SET apellidos = COALESCE(NULLIF(%s, ''), apellidos),
                    nombres = COALESCE(NULLIF(%s, ''), nombres),
                    fecha_nacimiento = COALESCE(NULLIF(%s, '')::date, fecha_nacimiento),
                    clase = COALESCE(NULLIF(%s, ''), clase)
                WHERE id=%s
            """, (apellidos, nombres, fecha_nac, clase, cid))
            return cid
        else:
            cur.execute("""
                INSERT INTO ciudadanos (dni, apellidos, nombres, fecha_nacimiento, clase)
                VALUES (%s,%s,%s, NULLIF(%s,'')::date, NULLIF(%s,''))
                RETURNING id
            """, (dni, apellidos, nombres, fecha_nac, clase))
            return cur.fetchone()[0]

def _upsert_servicio_militar(conn, ciudadano_id: int, unidad_alta: str, fecha_alta: str,
                             unidad_baja: str, fecha_baja: str, grado_baja: str):
    """Crea/actualiza fila 1:1 en servicio_militar para el ciudadano."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM servicio_militar WHERE ciudadano_id=%s", (ciudadano_id,))
        r = cur.fetchone()
        if r:
            cur.execute("""
                UPDATE servicio_militar
                SET unidad_alta = COALESCE(NULLIF(%s,''), unidad_alta),
                    fecha_alta  = COALESCE(NULLIF(%s,'')::date, fecha_alta),
                    unidad_baja = COALESCE(NULLIF(%s,''), unidad_baja),
                    fecha_baja  = COALESCE(NULLIF(%s,'')::date, fecha_baja),
                    grado_baja  = COALESCE(NULLIF(%s,''), grado_baja)
                WHERE ciudadano_id=%s
            """, (unidad_alta, fecha_alta, unidad_baja, fecha_baja, grado_baja, ciudadano_id))
        else:
            cur.execute("""
                INSERT INTO servicio_militar
                (ciudadano_id, unidad_alta, fecha_alta, unidad_baja, fecha_baja, grado_baja)
                VALUES (%s, NULLIF(%s,''), NULLIF(%s,'')::date, NULLIF(%s,''), NULLIF(%s,'')::date, NULLIF(%s,''))
            """, (ciudadano_id, unidad_alta, fecha_alta, unidad_baja, fecha_baja, grado_baja))

def _insert_documento(conn, ciudadano_id: int, tipo: str, ruta: str, pagina: int = None, hash_str: str = ""):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documentos (ciudadano_id, tipo, ruta, pagina, hash)
            VALUES (%s,%s,%s,%s,%s)
        """, (ciudadano_id, tipo, ruta, pagina, hash_str or ""))
    # sin RETURNING; es solo trazabilidad

def save_ocr_record(record: dict, source_path: str) -> bool:
    """
    Guarda un registro proveniente del OCR:
      - ciudadanos (upsert por DNI)
      - servicio_militar (upsert 1:1)
      - documentos (traza de origen)
    record keys esperadas (según app8): Nombres, Apellidos, DNI, Fecha de Nacimiento, Clase,
       Unidad de alta, Fecha de alta, Unidad de Baja, Fecha de baja, Grado
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        dni   = (record.get("DNI") or "").strip()
        noms  = (record.get("Nombres") or "").strip()
        apes  = (record.get("Apellidos") or "").strip()
        fnac  = (record.get("Fecha de Nacimiento") or "").strip()
        clase = (record.get("Clase") or "").strip()

        unidad_alta = (record.get("Unidad de alta") or "").strip()
        fecha_alta  = (record.get("Fecha de alta") or "").strip()
        unidad_baja = (record.get("Unidad de Baja") or "").strip()
        fecha_baja  = (record.get("Fecha de baja") or "").strip()
        grado       = (record.get("Grado") or "").strip()

        if not dni:
            print("[DB] ERROR save_ocr_record: DNI vacío; no se puede upsertar.")
            conn.close()
            return False

        cid = _get_or_create_ciudadano(conn, dni, apes, noms, fnac, clase)
        _upsert_servicio_militar(conn, cid, unidad_alta, fecha_alta, unidad_baja, fecha_baja, grado)
        _insert_documento(conn, cid, "OCR", source_path, None, "")  # hash opcional

        conn.commit()
        print(f"[DB] OCR guardado OK para ciudadano_id={cid}")
        return True
    except Exception as e:
        print(f"[DB] ERROR save_ocr_record: {e}")
        try: conn.rollback()
        except Exception: pass
        return False
    finally:
        try: conn.close()
        except Exception: pass

# Utilidad
def ping_db():
    """Prueba rápida desde consola: python -c "from db.db_connector import ping_db; print(ping_db())" """
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            print("[DB] Ping OK")
            return True
    except Exception as e:
        print(f"[DB] Ping ERROR: {e}")
        return False
    finally:
        conn.close()
