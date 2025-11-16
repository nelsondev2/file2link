import os
import time
from flask import Flask, send_from_directory, jsonify

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB
from load_manager import load_manager

app = Flask(__name__)

@app.route('/')
def home():
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nelson File2Link - Servidor de Archivos</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 40px;
                padding: 40px 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(10px);
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                margin-bottom: 10px;
                color: #2c3e50;
            }}
            
            .header p {{
                font-size: 1.2rem;
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
            
            .status-badge {{
                display: inline-block;
                background: #27ae60;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9rem;
            }}
            
            .btn {{
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
            }}
            
            .btn:hover {{
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }}
            
            .btn-telegram {{
                background: #0088cc;
            }}
            
            .btn-telegram:hover {{
                background: #0077b5;
            }}
            
            .info-section {{
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            }}
            
            .info-section h3 {{
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.4rem;
            }}
            
            .info-section p {{
                line-height: 1.6;
                margin-bottom: 10px;
                color: #5d6d7e;
            }}
            
            .code {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
            }}
            
            .features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }}
            
            .feature-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }}
            
            .feature-card:hover {{
                transform: translateY(-5px);
            }}
            
            .feature-icon {{
                font-size: 2.5rem;
                margin-bottom: 15px;
            }}
            
            .feature-card h4 {{
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 1.2rem;
            }}
            
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            
            .stat-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
            }}
            
            .stat-number {{
                font-size: 2rem;
                font-weight: bold;
                color: #3498db;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                font-size: 0.9rem;
                color: #7f8c8d;
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{
                    font-size: 2rem;
                }}
                
                .features {{
                    grid-template-columns: 1fr;
                }}
                
                .stats {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Nelson File2Link</h1>
                <div class="status-badge">✅ ACTIVO Y FUNCIONANDO</div>
                <p>Servidor profesional de archivos via Telegram</p>
                <p><strong>📏 Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB</strong></p>
                
                <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
                <a href="/system-status" class="btn">📊 Estado del Sistema</a>
                <a href="/health" class="btn">❤️ Health Check</a>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{MAX_FILE_SIZE_MB} MB</div>
                    <div class="stat-label">Límite por Archivo</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">📁</div>
                    <div class="stat-label">Sistema de Carpetas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">📦</div>
                    <div class="stat-label">Empaquetado ZIP</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">🔄</div>
                    <div class="stat-label">Cola Inteligente</div>
                </div>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">📁</div>
                    <h4>Almacenamiento Seguro</h4>
                    <p>Tus archivos almacenados de forma segura con enlaces permanentes y cifrado</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📦</div>
                    <h4>Empaquetado Simple</h4>
                    <p>Une todos tus archivos en un ZIP sin compresión para descargas rápidas</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔄</div>
                    <h4>Cola Inteligente</h4>
                    <p>Procesamiento automático de múltiples archivos en cola con progreso en tiempo real</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h4>Descargas Rápidas</h4>
                    <p>Sube y descarga archivos hasta {MAX_FILE_SIZE_MB}MB con enlaces directos</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🔐</div>
                    <h4>Acceso Seguro</h4>
                    <p>Cada usuario tiene su espacio privado con archivos organizados y protegidos</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🎯</div>
                    <h4>Fácil Gestión</h4>
                    <p>Renombra, elimina y organiza tus archivos fácilmente desde Telegram</p>
                </div>
            </div>

            <div class="info-section">
                <h3>📁 ¿Cómo funciona?</h3>
                <p>1. <strong>Envía cualquier archivo</strong> al bot de Telegram (@nelson_file2link_bot)</p>
                <p>2. <strong>El archivo se guarda</strong> en tu carpeta personal segura en el servidor</p>
                <p>3. <strong>Obtienes un enlace web permanente</strong> para compartir o descargar</p>
                <p>4. <strong>Gestiona tus archivos</strong> fácilmente desde cualquier dispositivo</p>

                <h3>🔗 Ejemplo de enlace de descarga:</h3>
                <div class="code">https://nelson-file2link.onrender.com/static/123456/downloads/mi_archivo.pdf</div>
                
                <h3>📁 Sistema de Carpetas:</h3>
                <div class="code">/cd downloads - Acceder a archivos de descarga
/cd packed - Acceder a archivos empaquetados
/list - Ver archivos en carpeta actual
/rename 3 nuevo_nombre - Renombrar archivo #3
/delete 5 - Eliminar archivo #5
/clear - Vaciar carpeta actual</div>
                
                <h3>📦 Comandos de Empaquetado:</h3>
                <div class="code">/pack - Crear ZIP con todos los archivos de descarga
/pack 100 - Dividir en partes de 100MB cada una</div>
                
                <h3>🔄 Comandos de Cola:</h3>
                <div class="code">/queue - Ver archivos en cola de procesamiento
/clearqueue - Limpiar cola de descargas</div>

                <h3>🔍 Comandos de Información:</h3>
                <div class="code">/status - Ver estado del sistema y uso de almacenamiento
/help - Mostrar ayuda completa
/cleanup - Limpiar archivos temporales</div>

                <h3>📏 Límites y Especificaciones:</h3>
                <div class="code">Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB
Archivos soportados: Documentos, Videos, Audio, Fotos
Formato de empaquetado: ZIP sin compresión
Máximo de procesos concurrentes: 1
Sistema optimizado para baja CPU</div>
            </div>

            <div class="info-section">
                <h3>🚀 Características Técnicas</h3>
                <p><strong>Arquitectura:</strong> Bot de Telegram + Servidor Web Flask</p>
                <p><strong>Almacenamiento:</strong> Sistema de archivos con estructura por usuario</p>
                <p><strong>Seguridad:</strong> Enlaces únicos por usuario y archivo</p>
                <p><strong>Rendimiento:</strong> Optimizado para entornos con recursos limitados</p>
                <p><strong>Escalabilidad:</strong> Procesamiento en cola para múltiples usuarios</p>
                
                <h3>🔧 Endpoints del API:</h3>
                <div class="code">/health - Verificación de estado del servicio
/system-status - Estado detallado del sistema
/static/[user_id]/downloads/[archivo] - Descargar archivos
/static/[user_id]/packed/[archivo] - Descargar archivos empaquetados</div>
            </div>

            <div class="info-section" style="text-align: center; background: #2c3e50; color: white;">
                <h3 style="color: white;">🤖 Nelson File2Link</h3>
                <p>Sistema profesional de gestión de archivos via Telegram</p>
                <p>Desarrollado para Render.com - Optimizado para bajos recursos</p>
                <p>© 2024 - Todos los derechos reservados</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Endpoint de health check para monitoreo"""
    return jsonify({
        "status": "online",
        "service": "nelson-file2link",
        "bot_status": "running",
        "timestamp": time.time(),
        "version": "2.0.0",
        "max_file_size_mb": MAX_FILE_SIZE_MB
    })

@app.route('/system-status')
def system_status():
    """Endpoint para verificar el estado detallado del sistema"""
    status = load_manager.get_status()
    
    # Obtener información del sistema de archivos
    storage_info = {
        "base_directory": BASE_DIR,
        "exists": os.path.exists(BASE_DIR),
        "total_files": 0,
        "total_size_mb": 0
    }
    
    if os.path.exists(BASE_DIR):
        total_size = 0
        total_files = 0
        for root, dirs, files in os.walk(BASE_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    total_files += 1
        
        storage_info.update({
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2)
        })
    
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-optimized",
        "timestamp": time.time(),
        "system_load": status,
        "storage": storage_info,
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_concurrent_processes": load_manager.max_processes,
            "cpu_usage_limit": status.get('cpu_percent', 0),
            "memory_usage_percent": status.get('memory_percent', 0),
            "optimized_for": "low-cpu-environment"
        },
        "endpoints": {
            "web_interface": "/",
            "health_check": "/health",
            "system_status": "/system-status",
            "file_download": "/static/<user_id>/<folder>/<filename>"
        }
    })

@app.route('/static/<path:path>')
def serve_static(path):
    """Sirve archivos estáticos de forma genérica"""
    try:
        return send_from_directory(BASE_DIR, path)
    except Exception as e:
        return jsonify({
            "error": "Archivo no encontrado",
            "path": path,
            "message": str(e)
        }), 404

@app.route('/static/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos de descarga con nombre original"""
    try:
        user_download_dir = os.path.join(BASE_DIR, user_id, "downloads")
        
        # Verificar que el directorio existe
        if not os.path.exists(user_download_dir):
            return jsonify({
                "error": "Usuario no encontrado",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo existe
        file_path = os.path.join(user_download_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "filename": filename,
                "user_id": user_id
            }), 404
        
        # Servir el archivo
        return send_from_directory(user_download_dir, filename)
        
    except Exception as e:
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

@app.route('/static/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados"""
    try:
        user_packed_dir = os.path.join(BASE_DIR, user_id, "packed")
        
        # Verificar que el directorio existe
        if not os.path.exists(user_packed_dir):
            return jsonify({
                "error": "Usuario no encontrado o sin archivos empaquetados",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo existe
        file_path = os.path.join(user_packed_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo empaquetado no encontrado",
                "filename": filename,
                "user_id": user_id
            }), 404
        
        # Servir el archivo
        return send_from_directory(user_packed_dir, filename)
        
    except Exception as e:
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "error": "Endpoint no encontrado",
        "message": "La ruta solicitada no existe",
        "available_endpoints": [
            "/",
            "/health", 
            "/system-status",
            "/static/<user_id>/downloads/<filename>",
            "/static/<user_id>/packed/<filename>"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado",
        "timestamp": time.time()
    }), 500

if __name__ == '__main__':
    # Solo para desarrollo local
    app.run(host='0.0.0.0', port=8080, debug=False)
