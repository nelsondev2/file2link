import os

# Configuración del Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_token_aqui")
BASE_URL = "https://nelson_file2link.onrender.com"
SERVER_DIR = "./server"

# Tamaños máximos (Telegram limita a 2GB para bots)
MAX_FILE_SIZE = 2000 * 1024 * 1024
CHUNK_SIZE = 8192

# Tipos de archivo permitidos (sin procesamiento de imágenes)
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'zip', 'rar', '7z', 'tar', 'gz',
    'mp3', 'wav', 'ogg',
    'mp4', 'avi', 'mkv', 'mov',
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',
    'py', 'js', 'html', 'css', 'json', 'xml'
}
