import os
import time
from flask import Flask, send_from_directory, jsonify

from config import BASE_DIR, RENDER_DOMAIN
from load_manager import load_manager

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nelson File2Link - Servidor de Archivos</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 40px;
                padding: 40px 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(10px);
            }
            
            .header h1 {
                font-size: 2.5rem;
                margin-bottom: 10px;
                color: #2c3e50;
            }
            
            .header p {
                font-size: 1.2rem;
                color: #7f8c8d;
                margin-bottom: 20px;
            }
            
            .status-badge {
                display: inline-block;
                background: #27ae60;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9rem;
            }
            
            .btn {
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 25px;
                margin: 10px;
                font-size: 1rem;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
            }
            
            .btn:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .btn-telegram {
                background: #0088cc;
            }
            
            .btn-telegram:hover {
                background: #0077b5;
            }
            
            .info-section {
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            }
            
            .info-section h3 {
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.4rem;
            }
            
            .info-section p {
                line-height: 1.6;
                margin-bottom: 10px;
                color: #5d6d7e;
            }
            
            .code {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
            }
            
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            
            .feature-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }
            
            .feature-card:hover {
                transform: translateY(-5px);
            }
            
            .feature-icon {
                font-size: 2.5rem;
                margin-bottom: 15px;
            }
            
            .feature-card h4 {
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 1.2rem;
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2rem;
                }
                
                .features {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Nelson File2Link</h1>
                <div class="status-badge">✅ ACTIVO Y FUNCIONANDO</div>
                <p>Servidor profesional de archivos via Telegram</p>
                
                <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">📁</div>
                    <h4>Almacenamiento Seguro</h4>
                    <p>Tus archivos almacenados de forma segura con enlaces permanentes</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📦</div>
                    <h4>Empaquetado Simple</h4>
                    <p>Une todos tus archivos en un ZIP sin compresión</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🎬</div>
                    <h4>Descargas YouTube</h4>
                    <p>Descarga videos de YouTube directamente a tu carpeta</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔄</div>
                    <h4>Cola Inteligente</h4>
                    <p>Procesamiento automático de múltiples archivos en cola</p>
                </div>
            </div>

            <div class="info-section">
                <h3>📁 ¿Cómo funciona?</h3>
                <p>1. Envía cualquier archivo al bot de Telegram</p>
                <p>2. El archivo se guarda en tu carpeta personal segura</p>
                <p>3. Obtienes un enlace web permanente para compartir</p>
                <p>4. Gestiona tus archivos fácilmente desde cualquier dispositivo</p>

                <h3>🔗 Ejemplo de enlace:</h3>
                <div class="code">https://nelson-file2link.onrender.com/static/123456/downloads/mi_archivo.pdf</div>
                
                <h3>🎬 Comando YouTube:</h3>
                <div class="code">/yt https://www.youtube.com/watch?v=ABCD1234</div>
                
                <h3>🔄 Comandos de Cola:</h3>
                <div class="code">/queue - Ver archivos en cola
/clearqueue - Limpiar cola de descargas</div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "online",
        "service": "nelson-file2link",
        "bot_status": "running",
        "timestamp": time.time()
    })

@app.route('/system-status')
def system_status():
    """Endpoint para verificar el estado del sistema"""
    status = load_manager.get_status()
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-optimized",
        "system_load": status,
        "timestamp": time.time(),
        "optimized_for": "low-cpu-environment",
        "max_concurrent_processes": load_manager.max_processes
    })

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/static/<user_id>/downloads/<filename>')  # CORREGIDO: downloads en lugar de download
def serve_download(user_id, filename):
    """Sirve archivos de descarga con nombre original - RUTA CORREGIDA"""
    user_download_dir = os.path.join(BASE_DIR, user_id, "downloads")  # CORREGIDO: downloads en lugar de download
    return send_from_directory(user_download_dir, filename)

@app.route('/static/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados"""
    user_packed_dir = os.path.join(BASE_DIR, user_id, "packed")
    return send_from_directory(user_packed_dir, filename)
