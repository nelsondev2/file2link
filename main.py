import os
import logging
import threading
import time
import sys
import gc
from waitress import serve

from config import BASE_DIR, PORT
from telegram_bot import TelegramBot
from flask_app import app

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ===== FUNCIÓN PARA LIMPIAR MEMORIA =====
def cleanup_memory():
    """Limpia memoria periódicamente"""
    try:
        logger.info("🧹 Limpiando memoria...")
        gc.collect()
        memory_info = "No disponible"
        try:
            import psutil
            process = psutil.Process()
            memory_info = f"{process.memory_info().rss / 1024 / 1024:.1f} MB"
        except:
            pass
        logger.info(f"Memoria después de limpieza: {memory_info}")
    except Exception as e:
        logger.error(f"Error limpiando memoria: {e}")

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask"""
    logger.info(f"Iniciando servidor web en puerto {PORT}")
    
    # Limpiar memoria antes de iniciar
    cleanup_memory()
    
    # Configurar waitress para usar menos recursos
    serve(app, host='0.0.0.0', port=PORT, threads=1, connection_limit=10)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    
    logger.info(f"Directorios creados/verificados: {BASE_DIR}")
    logger.info("🤖 Sistema optimizado para Render.com (0.1 CPU)")
    logger.info("📦 Límites activados para prevenir sobrecarga")

    # Limpiar memoria al inicio
    cleanup_memory()

    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()

    logger.info("Hilo del bot iniciado")

    time.sleep(10)

    logger.info("Iniciando servidor web principal...")

    start_web_server()
