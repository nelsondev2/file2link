from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN

from bot_handlers import (
    start_command,
    help_command,
    upload_command,
    list_files_command,
    handle_file_upload,
    button_handler
)

def main():
    """Función principal para ejecutar el bot"""
    # Crear aplicación
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers de comandos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("upload", upload_command))
    application.add_handler(CommandHandler("files", list_files_command))
    
    # Handler de archivos
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handle_file_upload
    ))
    
    # Handler de botones
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Iniciar bot
    print("🤖 Bot File2Link iniciado...")
    application.run_polling()

if __name__ == "__main__":
    main()
