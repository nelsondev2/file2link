import asyncio
import threading
from flask import Flask
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from config import BOT_TOKEN, SERVER_DIR, BASE_URL
from bot_handlers import (
    start_command,
    help_command,
    upload_command,
    list_files_command,
    handle_file_upload,
    button_handler,
    compress_command,
    delete_command
)

def create_flask_app():
    """Crear aplicación Flask"""
    app = Flask(__name__)

    @app.route('/')
    def index():
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🚀 File2Link Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; border-radius: 10px; }}
                .status {{ color: #4CAF50; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 File2Link Server</h1>
                    <p>Servidor de archivos funcionando correctamente</p>
                </div>
                <p>Este servidor proporciona enlaces de descarga directa para archivos subidos al bot de Telegram.</p>
                <p><strong>URL Base:</strong> {BASE_URL}</p>
                <p class="status">✅ Servidor activo y funcionando</p>
                <p><strong>🤖 Bot Status:</strong> <span style="color: green;">✅ Conectado</span></p>
            </div>
        </body>
        </html>
        """

    @app.route('/<path:file_path>')
    def serve_file(file_path):
        """Servir archivos estáticos"""
        import os
        from pathlib import Path
        from flask import send_file
        
        full_path = f"{SERVER_DIR}/{file_path}"
        
        # Verificar que el archivo existe y está dentro del directorio permitido
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return "Archivo no encontrado", 404
        
        # Verificar seguridad de la ruta
        try:
            file_obj = Path(full_path)
            server_path = Path(SERVER_DIR).resolve()
            
            # Asegurar que el archivo está dentro del directorio server
            if not str(file_obj.resolve()).startswith(str(server_path)):
                return "Acceso denegado", 403
        except Exception as e:
            return "Error de acceso", 403
        
        # Servir el archivo con nombre original
        filename = os.path.basename(full_path)
        return send_file(full_path, as_attachment=True, download_name=filename)

    @app.route('/health')
    def health_check():
        """Endpoint para verificar el estado del servidor"""
        from flask import jsonify
        return jsonify({
            "status": "ok", 
            "message": "Server is running",
            "base_url": BASE_URL,
            "bot_status": "connected"
        })
    
    return app

def run_flask_app():
    """Ejecutar aplicación Flask en un hilo separado"""
    app = create_flask_app()
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def run_bot():
    """Ejecutar bot de Telegram"""
    # Crear aplicación del bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers de comandos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", upload_command))
    application.add_handler(CommandHandler("files", list_files_command))
    application.add_handler(CommandHandler("compress", compress_command))
    application.add_handler(CommandHandler("delete", delete_command))
    
    # Handler de archivos
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handle_file_upload
    ))
    
    # Handler de botones
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Iniciar bot
    print("🤖 Starting Telegram Bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot started successfully!")
    return application

def main():
    """Función principal"""
    import os
    
    # Crear directorio server si no existe
    os.makedirs(SERVER_DIR, exist_ok=True)
    print(f"📁 Server directory created: {SERVER_DIR}")
    
    # Iniciar servidor Flask en un hilo separado
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Iniciar bot de Telegram en el hilo principal
    try:
        bot_app = asyncio.run(run_bot())
        
        # Mantener el programa corriendo
        print("🚀 Both Flask server and Telegram bot are running!")
        print("Press Ctrl+C to stop")
        
        # Mantener el hilo principal vivo
        try:
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping bot...")
            asyncio.run(bot_app.stop())
            asyncio.run(bot_app.shutdown())
            
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    main()
