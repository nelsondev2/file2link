import os
import math
import random
import logging
import time
from config import BASE_DIR, MAX_PART_SIZE_MB, RENDER_DOMAIN
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

class AdvancedPackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
        self.buffer_size = 64 * 1024  # 64KB buffer optimizado
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta archivos en ZIP o divide directamente sin cargar en RAM"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = [f for f in os.listdir(user_dir) 
                        if os.path.isfile(os.path.join(user_dir, f))]
                
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    # Usar división directa sin ZIP
                    result = self._pack_and_split_direct(user_id, user_dir, packed_dir, 
                                                        base_filename, split_size_mb, files)
                else:
                    # Usar ZIP normal sin compresión
                    result = self._pack_single_zip(user_id, user_dir, packed_dir, 
                                                  base_filename, files)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado avanzado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_zip(self, user_id, user_dir, packed_dir, base_filename, files):
        """Crea un único archivo ZIP sin compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            import zipfile
            
            logger.info(f"Creando ZIP con {len(files)} archivos...")
            
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    try:
                        zipf.write(file_path, filename)
                        logger.debug(f"Agregado: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")
                        continue
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", 
                                                f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': len(files)
            }], f"Empaquetado completado: {len(files)} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en ZIP simple: {e}")
            raise e
    
    def _pack_and_split_direct(self, user_id, user_dir, packed_dir, base_filename, 
                              split_size_mb, files):
        """Divide archivos directamente en partes sin ZIP intermedio - SIN CARGAR EN RAM"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # Calcular tamaño total
            total_size = 0
            file_sizes = {}
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                size = os.path.getsize(file_path)
                total_size += size
                file_sizes[filename] = size
            
            logger.info(f"Dividiendo {len(files)} archivos ({total_size/(1024*1024):.1f}MB) "
                       f"en partes de {split_size_mb}MB")
            
            # Calcular número de partes necesarias
            num_parts = math.ceil(total_size / split_size_bytes)
            logger.info(f"Se crearán {num_parts} partes")
            
            # Crear lista para almacenar información de partes
            parts_info = []  # Guarda (nombre_parte, tamaño, url)
            part_files_result = []  # Para retornar al usuario
            
            # Procesar archivos secuencialmente
            part_num = 1
            current_part_size = 0
            current_part_path = None
            current_part_file = None
            
            try:
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    file_size = file_sizes[filename]
                    
                    logger.info(f"Procesando: {filename} ({file_size/(1024*1024):.1f}MB)")
                    
                    with open(file_path, 'rb', buffering=self.buffer_size) as f:
                        bytes_remaining = file_size
                        
                        while bytes_remaining > 0:
                            # Si necesitamos una nueva parte
                            if current_part_file is None or current_part_size >= split_size_bytes:
                                if current_part_file:
                                    current_part_file.close()
                                    # Registrar parte anterior
                                    self._register_part_complete(
                                        part_num, current_part_path, user_id, 
                                        base_filename, parts_info, part_files_result, 
                                        len(files)
                                    )
                                    part_num += 1
                                    current_part_size = 0
                                
                                # Crear nueva parte
                                part_filename = f"{base_filename}.zip.{part_num:03d}"
                                current_part_path = os.path.join(packed_dir, part_filename)
                                current_part_file = open(current_part_path, 'wb', 
                                                        buffering=self.buffer_size)
                                logger.debug(f"Creada nueva parte: {part_filename}")
                            
                            # Calcular cuánto podemos escribir en esta parte
                            space_in_part = split_size_bytes - current_part_size
                            bytes_to_read = min(space_in_part, bytes_remaining, self.buffer_size)
                            
                            # Leer y escribir
                            chunk = f.read(bytes_to_read)
                            if not chunk:
                                break
                            
                            current_part_file.write(chunk)
                            current_part_size += len(chunk)
                            bytes_remaining -= len(chunk)
                
                # Registrar la última parte
                if current_part_file and current_part_size > 0:
                    current_part_file.close()
                    self._register_part_complete(
                        part_num, current_part_path, user_id, 
                        base_filename, parts_info, part_files_result, 
                        len(files)
                    )
            
            finally:
                # Asegurar cierre de archivos
                if current_part_file and not current_part_file.closed:
                    current_part_file.close()
            
            # Crear archivo de texto con lista de enlaces (FORMATO ORIGINAL)
            self._create_parts_list_file(user_id, packed_dir, base_filename, 
                                       parts_info, len(files))
            
            total_size_mb = sum(part['size_mb'] for part in part_files_result)
            
            return part_files_result, (f"✅ Empaquetado completado: {len(part_files_result)} partes, "
                                     f"{len(files)} archivos, {total_size_mb:.1f}MB total")
            
        except Exception as e:
            logger.error(f"Error en división directa: {e}", exc_info=True)
            # Limpiar archivos parciales
            for part_filename, _, _ in parts_info:
                part_path = os.path.join(packed_dir, part_filename)
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except:
                        pass
            raise e
    
    def _register_part_complete(self, part_num, part_path, user_id, base_filename, 
                               parts_info, part_files_result, total_files):
        """Registra una parte y guarda información para el archivo de lista"""
        part_size = os.path.getsize(part_path)
        part_size_mb = part_size / (1024 * 1024)
        
        part_filename = os.path.basename(part_path)
        
        # Registrar en file_service
        file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
        download_url = file_service.create_packed_url(user_id, part_filename)
        
        # Guardar información para el archivo de lista
        parts_info.append((part_filename, part_size, download_url))
        
        # Agregar al resultado para el usuario
        part_info = {
            'number': file_num,
            'filename': part_filename,
            'url': download_url,
            'size_mb': part_size_mb,
            'total_files': total_files if part_num == 1 else 0
        }
        
        part_files_result.append(part_info)
        logger.debug(f"Parte registrada: {part_filename} ({part_size_mb:.2f}MB)")
    
    def _create_parts_list_file(self, user_id, packed_dir, base_filename, 
                               parts_info, total_files):
        """Crea archivo .txt con lista de enlaces (FORMATO ORIGINAL SIMPLE)"""
        list_filename = f"{base_filename}.txt"
        list_path = os.path.join(packed_dir, list_filename)
        
        try:
            with open(list_path, 'w', encoding='utf-8') as f:
                # Formato SIMPLE igual al original - solo enlaces
                for part_filename, _, part_url in parts_info:
                    f.write(f"{part_url}\n\n")
            
            # Registrar archivo de lista en el sistema
            file_service.register_file(user_id, list_filename, list_filename, "packed")
            
            logger.info(f"Archivo de lista creado: {list_filename} ({len(parts_info)} enlaces)")
            return list_filename
            
        except Exception as e:
            logger.error(f"Error creando archivo de lista: {e}")
            return None
    
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


packing_service = AdvancedPackingService()
