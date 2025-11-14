import os

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "static"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 100
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# Configuración de YouTube
YT_DLP_TIMEOUT = 120  # 2 minutos máximo por descarga
YT_DLP_MAX_FILE_SIZE_MB = 500  # 500 mb

# Configuración de cookies (GLOBALES para todos los usuarios)
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")
COOKIES_GLOBAL_FILE = os.path.join(COOKIES_DIR, "global_cookies.txt")
