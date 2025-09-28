import os

# Configuración del Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_token_aqui")
BASE_URL = "https://nelson_file2link.onrender.com"
SERVER_DIR = "./server"

# Tamaños máximos
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB
CHUNK_SIZE = 8192
