# youtube_service.py
import os
import logging
import yt_dlp
import asyncio
import concurrent.futures
from config import BASE_DIR, YT_DLP_TIMEOUT, YT_DLP_MAX_FILE_SIZE_MB
from file_service import file_service
from load_manager import load_manager
from progress_service import progress_service

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[height<=360]',  # Máximo 360p
            'outtmpl': os.path.join(BASE_DIR, 'temp', '%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'max_filesize': YT_DLP_MAX_FILE_SIZE_MB * 1024 * 1024,  # Convertir a bytes
            'noprogress': True,  # Manejamos el progreso manualmente
        }
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(BASE_DIR, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

    async def download_youtube_video(self, url, user_id, progress_callback=None):
        """Descarga un video de YouTube y lo guarda en la carpeta del usuario"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return False, message

            try:
                # Verificar que sea una URL válida de YouTube
                if not await self._is_valid_youtube_url(url):
                    return False, "URL de YouTube no válida"

                # Obtener información del video
                video_info = await self._get_video_info(url)
                if not video_info:
                    return False, "No se pudo obtener información del video"

                # Configurar opciones de descarga
                user_dir = file_service.get_user_directory(user_id)
                original_filename = f"{video_info['title']}.mp4"
                sanitized_filename = file_service.sanitize_filename(original_filename)
                
                # Verificar si el archivo ya existe y generar nombre único
                final_filename = await self._get_unique_filename(user_dir, sanitized_filename)
                final_path = os.path.join(user_dir, final_filename)

                # Configurar opciones con la ruta final
                download_opts = self.ydl_opts.copy()
                download_opts['outtmpl'] = final_path

                # Descargar el video
                success, result = await self._download_video(url, download_opts, progress_callback)
                
                if success:
                    # Registrar el archivo en el sistema
                    file_number = file_service.register_file(user_id, original_filename, final_filename)
                    download_url = file_service.create_download_url(user_id, final_filename)
                    
                    file_size = os.path.getsize(final_path)
                    size_mb = file_size / (1024 * 1024)
                    
                    return True, {
                        'file_number': file_number,
                        'filename': original_filename,
                        'stored_filename': final_filename,
                        'url': download_url,
                        'size_mb': size_mb,
                        'duration': video_info.get('duration', 0),
                        'title': video_info['title']
                    }
                else:
                    return False, result

            except Exception as e:
                logger.error(f"Error en descarga de YouTube: {e}")
                return False, f"Error al descargar el video: {str(e)}"

            finally:
                load_manager.finish_process()

        except Exception as e:
            logger.error(f"Error en YouTubeService: {e}")
            return False, f"Error en el servicio de YouTube: {str(e)}"

    async def _is_valid_youtube_url(self, url):
        """Verifica si la URL es válida de YouTube"""
        youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com', 'm.youtube.com']
        return any(domain in url for domain in youtube_domains)

    async def _get_video_info(self, url):
        """Obtiene información del video sin descargarlo"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'video_sin_titulo'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Desconocido'),
                    'view_count': info.get('view_count', 0)
                }
        except Exception as e:
            logger.error(f"Error obteniendo info del video: {e}")
            return None

    async def _download_video(self, url, opts, progress_callback):
        """Descarga el video con manejo de progreso"""
        try:
            loop = asyncio.get_event_loop()
            
            def download():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.download([url])

            # Ejecutar en thread separado
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, download)
                await asyncio.wait_for(future, timeout=YT_DLP_TIMEOUT)
            
            return True, "Descarga completada"
            
        except asyncio.TimeoutError:
            return False, "La descarga tardó demasiado tiempo"
        except Exception as e:
            logger.error(f"Error en _download_video: {e}")
            return False, f"Error en descarga: {str(e)}"

    async def _get_unique_filename(self, directory, filename):
        """Genera un nombre de archivo único"""
        base, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename
        
        while os.path.exists(os.path.join(directory, new_filename)):
            new_filename = f"{base}_{counter}{ext}"
            counter += 1
            
        return new_filename

youtube_service = YouTubeService()
