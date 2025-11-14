import os
import logging
import requests
import asyncio
import concurrent.futures
import time
import urllib.parse
from config import DOWNLOAD_TIMEOUT, DOWNLOAD_MAX_FILE_SIZE_MB
from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service

logger = logging.getLogger(__name__)

class DownloadService:
    def __init__(self):
        self.max_file_size = DOWNLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
        
    async def download_from_url(self, url, user_id):
        """Descarga un archivo desde una URL y lo guarda en el sistema"""
        try:
            logger.info(f"🌐 Iniciando descarga desde URL: {url}")
            
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return False, message

            try:
                # Validar URL
                if not await self._validate_url(url):
                    return False, "❌ URL no válida o no accesible"

                # Obtener información del archivo
                file_info = await self._get_file_info(url)
                if not file_info:
                    return False, "❌ No se pudo obtener información del archivo"

                # Verificar tamaño
                if file_info['size'] > self.max_file_size:
                    size_mb = file_info['size'] / (1024 * 1024)
                    return False, f"❌ Archivo demasiado grande ({size_mb:.1f}MB). Máximo: {DOWNLOAD_MAX_FILE_SIZE_MB}MB"

                # Preparar descarga
                user_dir = file_service.get_user_directory(user_id, "downloads")
                filename = self._sanitize_filename(file_info['filename'])
                final_filename = await self._get_unique_filename(user_dir, filename)
                final_path = os.path.join(user_dir, final_filename)

                # Descargar archivo
                success, result = await self._download_file(url, final_path, file_info, user_id)
                
                if success:
                    # Registrar en sistema
                    file_number = file_service.register_file(user_id, filename, final_filename, "downloads")
                    download_url = file_service.create_download_url(user_id, final_filename)
                    
                    file_size = os.path.getsize(final_path)
                    size_mb = file_size / (1024 * 1024)
                    
                    logger.info(f"✅ Descarga exitosa: {filename} ({size_mb:.2f} MB)")
                    
                    return True, {
                        'file_number': file_number,
                        'filename': filename,
                        'stored_filename': final_filename,
                        'url': download_url,
                        'size_mb': size_mb,
                        'content_type': file_info.get('content_type', 'Desconocido')
                    }
                else:
                    return False, result

            except Exception as e:
                logger.error(f"❌ Error en descarga: {e}")
                return False, f"❌ Error en la descarga: {str(e)}"
                
            finally:
                load_manager.finish_process()

        except Exception as e:
            load_manager.finish_process()
            logger.error(f"❌ Error en download_from_url: {e}")
            return False, f"❌ Error del sistema: {str(e)}"

    async def _validate_url(self, url):
        """Valida que la URL sea accesible"""
        try:
            loop = asyncio.get_event_loop()
            
            def validate():
                try:
                    response = requests.head(url, timeout=10, allow_redirects=True)
                    return response.status_code == 200
                except:
                    return False
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, validate)
                return await asyncio.wait_for(future, timeout=15)
                
        except:
            return False

    async def _get_file_info(self, url):
        """Obtiene información del archivo desde la URL"""
        try:
            loop = asyncio.get_event_loop()
            
            def get_info():
                try:
                    response = requests.head(url, timeout=10, allow_redirects=True)
                    if response.status_code != 200:
                        return None
                    
                    # Obtener nombre del archivo
                    filename = self._extract_filename(url, response.headers)
                    
                    # Obtener tamaño
                    size = 0
                    if 'content-length' in response.headers:
                        try:
                            size = int(response.headers['content-length'])
                        except:
                            size = 0
                    
                    # Obtener tipo de contenido
                    content_type = response.headers.get('content-type', 'application/octet-stream')
                    
                    return {
                        'filename': filename,
                        'size': size,
                        'content_type': content_type,
                        'headers': dict(response.headers)
                    }
                except Exception as e:
                    logger.error(f"Error obteniendo info: {e}")
                    return None
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, get_info)
                return await asyncio.wait_for(future, timeout=15)
                
        except Exception as e:
            logger.error(f"Error en _get_file_info: {e}")
            return None

    def _extract_filename(self, url, headers):
        """Extrae el nombre del archivo desde la URL o headers"""
        # Intentar desde Content-Disposition header
        if 'content-disposition' in headers:
            cd = headers['content-disposition']
            if 'filename=' in cd:
                filename = cd.split('filename=')[1].strip('"\'')
                if filename:
                    return filename
        
        # Intentar desde la URL
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if path and '/' in path:
            filename = path.split('/')[-1]
            if filename and '.' in filename:
                return filename
        
        # Nombre por defecto
        return f"archivo_descargado_{int(time.time())}.bin"

    async def _download_file(self, url, file_path, file_info, user_id):
        """Descarga el archivo con progreso"""
        try:
            loop = asyncio.get_event_loop()
            
            def download_with_progress():
                try:
                    # Configurar sesión con headers
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.5',
                    })
                    
                    # Descargar con stream
                    response = session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    start_time = time.time()
                    
                    with open(file_path, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                file.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # Calcular progreso (podría integrarse con progress_service)
                                elapsed_time = time.time() - start_time
                                speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                                
                                # Log cada 5MB o cuando se complete
                                if downloaded_size % (5 * 1024 * 1024) == 0 or downloaded_size == total_size:
                                    percent = (downloaded_size / total_size * 100) if total_size > 0 else 0
                                    logger.info(f"📥 Descargando: {percent:.1f}% - {speed/1024/1024:.1f} MB/s")
                    
                    # Verificar descarga completa
                    if total_size > 0 and downloaded_size != total_size:
                        raise Exception(f"Descarga incompleta: {downloaded_size}/{total_size} bytes")
                    
                    return True, "Descarga completada"
                    
                except requests.exceptions.Timeout:
                    return False, "⏰ Timeout en la descarga"
                except requests.exceptions.HTTPError as e:
                    return False, f"❌ Error HTTP: {e.response.status_code}"
                except requests.exceptions.RequestException as e:
                    return False, f"❌ Error de conexión: {str(e)}"
                except Exception as e:
                    return False, f"❌ Error en descarga: {str(e)}"
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, download_with_progress)
                result = await asyncio.wait_for(future, timeout=DOWNLOAD_TIMEOUT + 30)
                return result
                
        except asyncio.TimeoutError:
            return False, "⏰ La descarga tardó demasiado tiempo"
        except Exception as e:
            logger.error(f"❌ Error en _download_file: {e}")
            return False, f"❌ Error en el proceso de descarga: {str(e)}"

    def _sanitize_filename(self, filename):
        """Limpia el nombre de archivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        # Limitar longitud
        filename = filename.strip()
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        return filename

    async def _get_unique_filename(self, directory, filename):
        """Genera nombre único"""
        base, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename
        
        while os.path.exists(os.path.join(directory, new_filename)):
            new_filename = f"{base}_{counter}{ext}"
            counter += 1
            
        return new_filename

    def cleanup_temp_files(self, max_age_hours=1):
        """Limpia archivos temporales (si los hay)"""
        pass

download_service = DownloadService()
