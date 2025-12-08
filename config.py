import os

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada (0.1 CPU en plan gratis)
MAX_PART_SIZE_MB = 500  # ⬅️ REDUCIDO a 500 MB para ser más realista
COMPRESSION_TIMEOUT = 300  # ⬅️ REDUCIDO a 5 minutos
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 70  # ⬅️ REDUCIDO para ser más conservador

# ✅ Tamaño máximo de archivos configurable
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# ⬇️ Configuración para descarga rápida
DOWNLOAD_BUFFER_SIZE = 65536  # ⬅️ REDUCIDO a 64KB para usar menos memoria
DOWNLOAD_THREADS = 1  # ⬅️ REDUCIDO a 1 para usar menos CPU
DOWNLOAD_TIMEOUT = 7200  # ⬅️ AUMENTADO a 2 horas para archivos grandes
MAX_RETRIES = 5  # ⬅️ AUMENTADO para archivos grandes
CHUNK_SIZE = 32768  # ⬅️ REDUCIDO a 32KB para usar menos memoria

# ⬇️ NUEVO: Límites para empaquetado de archivos grandes
MAX_TOTAL_SIZE_FOR_PACKING_MB = 1000  # ⬅️ Máximo total para empaquetar
MAX_FILES_FOR_PACKING = 20  # ⬅️ Máximo número de archivos para empaquetar
