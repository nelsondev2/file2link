import os
import logging
import threading
import time
import sys
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

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask con Waitress optimizado para velocidad"""
    logger.info(f"Iniciando servidor web optimizado en puerto {PORT}")
    
    # Configuración optimizada para alta velocidad
    serve(
        app, 
        host='0.0.0.0', 
        port=PORT,
        threads=100,  # Más threads para múltiples conexiones
        connection_limit=1000,  # Límite alto de conexiones
        channel_timeout=300,  # 5 minutos timeout para descargas grandes
        cleanup_interval=30,  # Limpieza más frecuente
        asyncore_loop_timeout=1,
        send_bytes=8192,  # Buffer de envío aumentado a 8KB
        outbuf_overflow=8388608,  # 8MB buffer de salida
        inbuf_overflow=8388608,  # 8MB buffer de entrada
        receive_bytes=8192,  # Buffer de recepción aumentado a 8KB
        expose_tracebacks=False,  # Deshabilitar tracebacks en producción
        url_scheme='https',  # Forzar HTTPS
        ident=None  # Sin identificación del servidor
    )

if __name__ == '__main__':
    # Crear directorios necesarios
    os.makedirs(BASE_DIR, exist_ok=True)
    
    logger.info(f"Directorios creados/verificados: {BASE_DIR}")
    logger.info("⚡ Configuración optimizada para descargas de alta velocidad")
    logger.info(f"📊 Chunk size: {2}MB, Buffer size: {4}MB")

    # Iniciar bot de Telegram en hilo separado
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()

    logger.info("🤖 Hilo del bot iniciado")

    # Esperar a que el bot se inicie completamente
    time.sleep(10)

    logger.info("🚀 Iniciando servidor web principal optimizado...")
    logger.info("📈 Configuración para máxima velocidad activada")

    # Iniciar servidor web principal
    start_web_server()
