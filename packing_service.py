import os
import zipfile
import time
import logging
import sys
import concurrent.futures
from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

class SimplePackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta la carpeta del usuario con división ZIP nativa"""
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
                
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    result = self._pack_split_zipfile(user_id, user_dir, packed_dir, base_filename, split_size_mb)
                else:
                    result = self._pack_single_simple(user_id, user_dir, packed_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_simple(self, user_id, user_dir, packed_dir, base_filename):
        """Empaqueta en un solo archivo ZIP SIN compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Empaquetando {total_files} archivos en {output_file}")
            
            # Crear ZIP con todos los archivos
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename}")
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
            logger.error(f"Error en _pack_single_simple: {e}")
            raise e
    
    def _pack_split_zipfile(self, user_id, user_dir, packed_dir, base_filename, split_size_mb):
        """Crea un archivo ZIP dividido nativo usando ZipFile directamente"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            # Contador para partes
            part_num = 1
            part_files = []
            current_part_size = 0
            current_zip = None
            
            logger.info(f"Creando archivo ZIP dividido en partes de {split_size_mb}MB")
            
            # Procesar cada archivo
            for idx, (filename, file_path) in enumerate(all_files):
                file_size = os.path.getsize(file_path)
                
                # Si no hay ZIP actual o añadir este archivo excedería el tamaño máximo
                if current_zip is None or (current_part_size + file_size > split_size_bytes):
                    # Cerrar ZIP anterior si existe
                    if current_zip is not None:
                        current_zip.close()
                    
                    # Crear nuevo archivo ZIP
                    part_filename = f"{base_filename}.zip.part{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    current_zip = zipfile.ZipFile(part_path, 'w', compression=zipfile.ZIP_STORED)
                    current_part_size = 0
                    
                    # Registrar la parte anterior
                    if part_num > 1:
                        previous_part_filename = f"{base_filename}.zip.part{part_num-1:03d}"
                        previous_part_path = os.path.join(packed_dir, previous_part_filename)
                        previous_size = os.path.getsize(previous_part_path)
                        
                        file_num = file_service.register_file(user_id, previous_part_filename, previous_part_filename, "packed")
                        download_url = file_service.create_packed_url(user_id, previous_part_filename)
                        
                        part_files.append({
                            'number': file_num,
                            'filename': previous_part_filename,
                            'url': download_url,
                            'size_mb': previous_size / (1024 * 1024)
                        })
                
                # Añadir archivo al ZIP actual
                try:
                    current_zip.write(file_path, filename)
                    current_part_size += file_size
                    logger.info(f"Agregado a parte {part_num}: {filename} ({file_size/(1024*1024):.1f}MB)")
                except Exception as e:
                    logger.error(f"Error agregando {filename} al ZIP parte {part_num}: {e}")
                    continue
                
                # Si hemos alcanzado el límite, pasar a siguiente parte
                if current_part_size >= split_size_bytes:
                    current_zip.close()
                    part_num += 1
                    current_zip = None
            
            # Cerrar el último ZIP si existe
            if current_zip is not None:
                current_zip.close()
                
                # Registrar la última parte
                last_part_filename = f"{base_filename}.zip.part{part_num:03d}"
                last_part_path = os.path.join(packed_dir, last_part_filename)
                last_size = os.path.getsize(last_part_path)
                
                file_num = file_service.register_file(user_id, last_part_filename, last_part_filename, "packed")
                download_url = file_service.create_packed_url(user_id, last_part_filename)
                
                part_files.append({
                    'number': file_num,
                    'filename': last_part_filename,
                    'url': download_url,
                    'size_mb': last_size / (1024 * 1024)
                })
            
            total_size = sum(part['size_mb'] for part in part_files)
            return part_files, f"Empaquetado completado: {len(part_files)} partes, {total_files} archivos, {total_size:.1f}MB total"
            
        except Exception as e:
            logger.error(f"Error en _pack_split_zipfile: {e}")
            raise e

    def clear_packed_folder(self, user_id):
        """Elimina todos los archivos empaquetados del usuario"""
        try:
            packed_dir = file_service.get_user_directory(user_id, "packed")
            
            if not os.path.exists(packed_dir):
                return False, "No tienes archivos empaquetados para eliminar"
            
            files = os.listdir(packed_dir)
            if not files:
                return False, "No tienes archivos empaquetados para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(packed_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            return True, f"Se eliminaron {deleted_count} archivos empaquetados"
            
        except Exception as e:
            logger.error(f"Error limpiando carpeta empaquetada: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

packing_service = SimplePackingService()
