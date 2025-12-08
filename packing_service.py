import os
import zipfile
import time
import logging
import sys
import concurrent.futures
import shutil
from config import BASE_DIR, MAX_PART_SIZE_MB, MAX_TOTAL_SIZE_FOR_PACKING_MB, MAX_FILES_FOR_PACKING
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

class OptimizedPackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
        self.max_total_size_mb = MAX_TOTAL_SIZE_FOR_PACKING_MB
        self.max_files = MAX_FILES_FOR_PACKING
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta la carpeta del usuario con optimización para bajos recursos"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = os.listdir(user_dir)
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                # ⬇️ NUEVO: Verificar límites antes de empezar
                total_size_bytes = 0
                valid_files = []
                
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        total_size_bytes += file_size
                        valid_files.append((filename, file_path, file_size))
                
                total_size_mb = total_size_bytes / (1024 * 1024)
                
                # Validar límites
                if len(valid_files) > self.max_files:
                    return None, f"Demasiados archivos ({len(valid_files)}). Máximo permitido: {self.max_files}"
                
                if total_size_mb > self.max_total_size_mb:
                    return None, f"Total demasiado grande ({total_size_mb:.1f} MB). Máximo: {self.max_total_size_mb} MB"
                
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    # ⬇️ USAR MÉTODO OPTIMIZADO PARA BAJOS RECURSOS
                    result = self._pack_and_split_optimized(user_id, valid_files, packed_dir, base_filename, split_size_mb, total_size_mb)
                else:
                    result = self._pack_single_optimized(user_id, valid_files, packed_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado: {e}", exc_info=True)
            return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_optimized(self, user_id, file_list, packed_dir, base_filename):
        """Empaqueta en un solo archivo ZIP optimizado para bajos recursos"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            total_files = len(file_list)
            
            logger.info(f"Empaquetando {total_files} archivos en {output_file} (tamaño total: {sum(f[2] for f in file_list)/(1024*1024):.1f} MB)")
            
            # Crear ZIP con chunks para usar menos memoria
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path, file_size in file_list:
                    try:
                        # ⬇️ AGREGAR ARCHIVOS EN CHUNKS PEQUEÑOS
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado: {filename} ({file_size/(1024*1024):.1f} MB)")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo empaquetado
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': total_files
            }], f"Empaquetado completado: {total_files} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en _pack_single_optimized: {e}", exc_info=True)
            raise e
    
    def _pack_and_split_optimized(self, user_id, file_list, packed_dir, base_filename, split_size_mb, total_size_mb):
        """Crea un archivo ZIP y lo divide optimizado para bajos recursos"""
        # Limitar el split size al máximo configurado
        split_size_mb = min(split_size_mb, self.max_part_size_mb)
        split_size_bytes = split_size_mb * 1024 * 1024
        
        try:
            total_files = len(file_list)
            
            logger.info(f"Creando archivo ZIP y dividiendo en partes de {split_size_mb}MB")
            logger.info(f"Total: {total_files} archivos, {total_size_mb:.1f} MB")
            
            # PASO 1: Crear el archivo ZIP temporal en chunks
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            # ⬇️ CREAR ZIP EN MODO APPEND PARA USAR MENOS MEMORIA
            with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path, file_size in file_list:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename} ({file_size/(1024*1024):.1f} MB)")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            zip_size = os.path.getsize(temp_zip_path)
            logger.info(f"ZIP creado: {temp_zip_path} ({zip_size/(1024*1024):.2f}MB)")
            
            # PASO 2: Dividir el archivo ZIP en partes con chunks pequeños
            part_files = []
            part_num = 1
            
            # ⬇️ LEER Y ESCRIBIR EN CHUNKS PEQUEÑOS
            chunk_size = 1024 * 1024  # 1 MB chunks
            
            with open(temp_zip_path, 'rb') as zip_file:
                while True:
                    part_filename = f"{base_filename}.zip.{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    bytes_written = 0
                    
                    with open(part_path, 'wb') as part_file:
                        while bytes_written < split_size_bytes:
                            # Calcular cuánto leer
                            remaining_in_part = split_size_bytes - bytes_written
                            chunk_to_read = min(chunk_size, remaining_in_part)
                            
                            # Leer chunk
                            chunk = zip_file.read(chunk_to_read)
                            if not chunk:
                                break
                            
                            # Escribir chunk
                            part_file.write(chunk)
                            bytes_written += len(chunk)
                            
                            # Si llegamos al final del archivo
                            if len(chunk) < chunk_to_read:
                                break
                    
                    # Si no escribimos nada, salir del loop
                    if bytes_written == 0:
                        os.remove(part_path)
                        break
                    
                    part_size_mb = bytes_written / (1024 * 1024)
                    
                    # Registrar la parte
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
                    download_url = file_service.create_packed_url(user_id, part_filename)
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size_mb,
                        'total_files': total_files if part_num == 1 else 0  # Solo el primero tiene el total
                    })
                    
                    logger.info(f"Parte {part_num} creada: {part_filename} ({part_size_mb:.2f}MB)")
                    part_num += 1
                    
                    # Si llegamos al final del archivo
                    if bytes_written < split_size_bytes:
                        break
            
            # Eliminar el archivo ZIP temporal
            os.remove(temp_zip_path)
            logger.info(f"Archivo temporal eliminado: {temp_zip_path}")
            
            # Verificar que se crearon partes
            if not part_files:
                return None, "No se crearon partes. Error en la división del archivo."
            
            total_size_mb = sum(part['size_mb'] for part in part_files)
            
            return part_files, f"✅ Empaquetado completado: {len(part_files)} partes, {total_files} archivos, {total_size_mb:.1f}MB total"
            
        except MemoryError:
            logger.error("ERROR DE MEMORIA: Sistema sin suficiente memoria para procesar")
            # Limpiar archivos temporales
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
            return None, "❌ Error de memoria: Archivo demasiado grande para procesar. Intenta con archivos más pequeños."
            
        except Exception as e:
            logger.error(f"Error en _pack_and_split_optimized: {e}", exc_info=True)
            # Limpiar archivos temporales en caso de error
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
            raise e
    
    def get_packing_limits(self):
        """Devuelve los límites actuales de empaquetado"""
        return {
            'max_part_size_mb': self.max_part_size_mb,
            'max_total_size_mb': self.max_total_size_mb,
            'max_files': self.max_files
        }

packing_service = OptimizedPackingService()
