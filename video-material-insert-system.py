import sys, os, tempfile, shutil, atexit
from pathlib import Path

# ── Embedded build key (AES-256, do not modify) ─────────────────────────
_DB_KEY = bytes.fromhex("7bd436c99721ee59feffd31fdaaf3eb62c4bee9780db118f8c641e0f0c52b695")

# ── Runtime paths ────────────────────────────────────────────────────────
_EXE_DIR     = Path(sys.argv[0]).resolve().parent
_DB_ENC      = _EXE_DIR / "data" / "database.db.enc"
_DB_PLAIN    = _EXE_DIR / "data" / "database.db"
_DB_WORK_DIR = Path(tempfile.mkdtemp(prefix='_vfdb_'))
_DB_WORK     = _DB_WORK_DIR / "database.db"


# 5-byte magic header written at the start of every encrypted file.
# Used to detect whether a file is already encrypted before acting.
_ENC_MAGIC = b'VFDB\x01'


def _is_enc(path: Path) -> bool:
    """Return True only if path exists and starts with our encryption magic."""
    try:
        return path.stat().st_size >= 37 and path.read_bytes()[:5] == _ENC_MAGIC
    except OSError:
        return False


def _aes_enc(src: Path, dst: Path, key: bytes) -> None:
    """Encrypt src → dst. Skips silently if src is already encrypted."""
    if _is_enc(src):
        print(f'[INFO] {src.name} is already encrypted — skipped.', flush=True)
        if src != dst:
            import shutil as _sh; _sh.copy2(str(src), str(dst))
        return
    from Crypto.Cipher import AES
    cipher = AES.new(key, AES.MODE_EAX)
    ct, tag = cipher.encrypt_and_digest(src.read_bytes())
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(_ENC_MAGIC + cipher.nonce + tag + ct)


def _aes_dec(src: Path, dst: Path, key: bytes) -> None:
    """Decrypt src → dst. Raises ValueError if src is not an encrypted file."""
    if not _is_enc(src):
        raise ValueError(f'{src.name} is not an encrypted database file.')
    from Crypto.Cipher import AES
    raw = src.read_bytes()[5:]  # strip magic
    cipher = AES.new(key, AES.MODE_EAX, nonce=raw[:16])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(cipher.decrypt_and_verify(raw[32:], raw[16:32]))


# ── Migration / session setup ─────────────────────────────────────────────
if _DB_PLAIN.exists():
    if _is_enc(_DB_PLAIN):
        # File was misnamed — just rename it to .enc
        print('[INFO] database.db detected as already encrypted — renaming to .enc.', flush=True)
        _DB_PLAIN.rename(_DB_ENC)
    elif not _DB_ENC.exists():
        # Genuine plaintext SQLite — encrypt it now
        _aes_enc(_DB_PLAIN, _DB_ENC, _DB_KEY)
        _DB_PLAIN.unlink()
        print('[INFO] Database encrypted on first run.', flush=True)
    else:
        # Both files exist — use encrypted, leave plain as backup
        print('[WARN] Both database.db and database.db.enc found; using encrypted version.', flush=True)

if _DB_ENC.exists():
    _aes_dec(_DB_ENC, _DB_WORK, _DB_KEY)

# Override DATABASE_URL so SQLAlchemy uses the decrypted working copy
os.environ["DATABASE_URL"] = "sqlite:///" + str(_DB_WORK).replace("\\", "/")


def _on_exit() -> None:
    if _DB_WORK.exists():
        if _is_enc(_DB_WORK):
            # Work file somehow already encrypted — do not double-encrypt
            print('[WARN] Work database is already encrypted — skipping re-encrypt.', flush=True)
            import shutil as _sh; _sh.copy2(str(_DB_WORK), str(_DB_ENC))
        else:
            _aes_enc(_DB_WORK, _DB_ENC, _DB_KEY)
    shutil.rmtree(str(_DB_WORK_DIR), ignore_errors=True)


atexit.register(_on_exit)

# ── Application import ───────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.main import app

# ── Entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    _port = int(os.environ.get("PORT", "8000"))
    print("\n  ┌─────────────────────────────────────────────────┐", flush=True)
    print(f"  │  Frontend UI : http://localhost:{_port}/           │", flush=True)
    print(f"  │  Backend API : http://localhost:{_port}/api        │", flush=True)
    print(f"  │  API Docs    : http://localhost:{_port}/docs       │", flush=True)
    print("  │  Press Ctrl+C to stop                           │", flush=True)
    print("  └─────────────────────────────────────────────────┘\n", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=_port, log_level="info")
