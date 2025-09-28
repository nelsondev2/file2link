from flask import Flask, send_file, request
import os
from pathlib import Path
from config import SERVER_DIR, BASE_URL

app = Flask(__name__)

@app.route('/')
def index():
    return "🚀 File2Link Server - Servidor de archivos funcionando correctamente"

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
        if not file_obj.resolve().is_relative_to(Path(SERVER_DIR).resolve()):
            return "Acceso denegado", 403
    except Exception:
        return "Error de acceso", 403
    
    # Servir el archivo
    return send_file(full_path)

if __name__ == '__main__':
    # Crear directorio server si no existe
    os.makedirs(SERVER_DIR, exist_ok=True)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
