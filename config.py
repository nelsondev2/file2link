import os

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "storage"  # ⬅️ CAMBIADO de "static" a "storage"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 100
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# ✅ Tamaño máximo de archivos configurable
MAX_FILE_SIZE_MB = 2000  # 2000MB por defecto
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Cálculo automático en bytes

# ===== CONFIGURACIÓN DE VELOCIDAD DE DESCARGA =====
CHUNK_SIZE = 1024 * 1024 * 2  # 2MB chunks para descargas rápidas
SENDFILE_BUFFER_SIZE = 1024 * 1024 * 4  # 4MB buffer para lectura de archivos
MAX_DOWNLOAD_THREADS = 100  # Máximo de threads para descargas concurrentes
DOWNLOAD_TIMEOUT = 300  # 5 minutos de timeout para descargas grandes
USE_X_SENDFILE = True  # Usar X-SendFile si está disponible
ENABLE_COMPRESSION = True  # Habilitar compresión Gzip
