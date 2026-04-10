import os

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "14681595"))
API_HASH = os.getenv("API_HASH", "a86730aab5c59953c424abb4396d32d5")  # Este es un token, NO un API_HASH
BOT_TOKEN = os.getenv("BOT_TOKEN", "8534765454:AAFyWB3TFWLZKcDu0RNC1hCMwSMqQZ9_-3g")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://file2link-4dye.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 500
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# ✅ Tamaño máximo de archivos configurable
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# ⬇️ Configuración para descarga rápida
DOWNLOAD_BUFFER_SIZE = 131072
DOWNLOAD_THREADS = 2
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 65536