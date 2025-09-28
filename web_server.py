from flask import Flask, send_file, request, jsonify
import os
from pathlib import Path
from config import SERVER_DIR, BASE_URL

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🚀 File2Link Server</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .header { background: #4CAF50; color: white; padding: 20px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 File2Link Server</h1>
                <p>Servidor de archivos funcionando correctamente</p>
            </div>
            <p>Este servivo proporciona enlaces de descarga directa para archivos subidos al bot de Telegram.</p>
            <p><strong>URL Base:</strong> {BASE_URL}</p>
        </div>
    </body>
    </html>
    """.format(BASE_URL=BASE_URL)

@app.route('/<path:file_path>')
def serve_file(file_path):
    """Servir archivos estáticos"""
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
    return jsonify({"status": "ok", "message": "Server is running"})

if __name__ == '__main__':
    # Crear directorio server si no existe
    os.makedirs(SERVER_DIR, exist_ok=True)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
