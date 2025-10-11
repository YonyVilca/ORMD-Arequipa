# services/auth_service.py
import bcrypt

def hash_password(plain_password: str, rounds: int = 12) -> str:
    """Genera hash bcrypt para guardar en BD."""
    if not isinstance(plain_password, str) or not plain_password:
        raise ValueError("La contraseña no puede estar vacía.")
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode()

def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica un password contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False
