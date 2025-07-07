"""
Qlik App Lifecycle Tools

This module provides methods for app lifecycle management including
export, import, copy, and publish operations.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from .qlik_cli_base import QlikCLI, QlikCLIError

# Configure logging
logger = logging.getLogger(__name__)


class QlikAppLifecycleMixin:
    """Mixin class for app lifecycle operations"""
    
    def app_export(self, 
                   app_identifier: str,
                   output_path: str,
                   format: str = 'qvf',
                   include_data: bool = True,
                   no_data: bool = False) -> Dict[str, Any]:
        """
        Export Qlik application to local file for backup, migration, or version control
        
        Args:
            app_identifier: App ID or name to export
            output_path: Path where exported file will be saved
            format: Export format ('qvf', 'json', 'xlsx')
            include_data: Whether to include data in export (default: True)
            no_data: Export without data (only metadata/script) (default: False)
            
        Returns:
            Dictionary containing export result and file information
            
        Raises:
            QlikCLIError: If export fails or parameters are invalid
        """
        logger.info(f"Exporting Qlik app '{app_identifier}' to '{output_path}' in format '{format}'")
        
        # Validate parameters
        if not app_identifier or not app_identifier.strip():
            raise QlikCLIError("App identifier cannot be empty")
        
        if not output_path or not output_path.strip():
            raise QlikCLIError("Output path cannot be empty")
        
        if not self._validate_export_format(format):
            raise QlikCLIError(f"Invalid export format: {format}. Valid formats: qvf, json, xlsx")
        
        # Handle conflicting data parameters
        if no_data and include_data:
            logger.warning("Both no_data and include_data specified. Using no_data=True")
            include_data = False
        
        # Validate and prepare output path
        output_file = Path(output_path)
        output_dir = output_file.parent
        
        # Ensure output directory exists
        if not self._ensure_directory_exists(str(output_dir)):
            raise QlikCLIError(f"Cannot create output directory: {output_dir}")
        
        # Check disk space (estimate 100MB minimum for safety)
        available_space = self._get_available_disk_space(str(output_dir))
        if available_space != -1 and available_space < 100 * 1024 * 1024:  # 100MB
            raise QlikCLIError(f"Insufficient disk space. Available: {available_space / (1024*1024):.1f}MB")
        
        # Validate app exists before attempting export
        try:
            app_details = self.app_get(app_identifier)
            if not app_details['success']:
                raise QlikCLIError(f"App '{app_identifier}' not found or not accessible")
        except QlikCLIError as e:
            raise QlikCLIError(f"Cannot validate app before export: {str(e)}")
        
        # Build export command
        cmd = self._build_base_command()
        cmd.extend(['app', 'export'])
        
        # Add app identifier
        cmd.extend(['--app', app_identifier])
        
        # Add output path
        cmd.extend(['--output', str(output_path)])
        
        # Add format if not default qvf
        if format.lower() != 'qvf':
            cmd.extend(['--format', format.lower()])
        
        # Add data options
        if no_data or not include_data:
            cmd.append('--no-data')
        
        # Track start time for duration calculation
        start_time = time.time()
        temp_files = []
        
        try:
            # Execute export command
            result = self._execute_command(cmd)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Verify output file was created
            if not output_file.exists():
                raise QlikCLIError(f"Export completed but output file not found: {output_path}")
            
            # Get file size
            file_size = output_file.stat().st_size
            
            logger.info(f"Successfully exported app '{app_identifier}' to '{output_path}' ({file_size} bytes, {duration:.2f}s)")
            
            return {
                'success': True,
                'app_identifier': app_identifier,
                'output_path': str(output_path),
                'format': format.lower(),
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'include_data': include_data and not no_data,
                'export_duration_seconds': round(duration, 2),
                'command_result': result
            }
            
        except QlikCLIError as e:
            # Clean up any partial files on failure
            if output_file.exists():
                try:
                    output_file.unlink()
                    logger.info(f"Cleaned up partial export file: {output_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up partial file {output_path}: {cleanup_error}")
            
            error_msg = f"Failed to export app '{app_identifier}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except Exception as e:
            # Clean up any partial files on unexpected errors
            if output_file.exists():
                try:
                    output_file.unlink()
                except Exception:
                    pass
            
            error_msg = f"Unexpected error during app export: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        finally:
            # Clean up any temporary files
            for temp_file in temp_files:
                try:
                    if Path(temp_file).exists():
                        Path(temp_file).unlink()
                except Exception:
                    pass
    
    def app_import(self,
                   file_path: str,
                   app_name: Optional[str] = None,
                   space_id: Optional[str] = None,
                   replace_existing: bool = False,
                   validate_before_import: bool = True) -> Dict[str, Any]:
        """
        Import Qlik application from local file to create new app in tenant
        
        Args:
            file_path: Path to import file (QVF format)
            app_name: Name for new app (optional, will use file name if not provided)
            space_id: Target space for import (optional, uses personal space if not provided)
            replace_existing: Whether to replace existing app with same name
            validate_before_import: Whether to validate file before import
            
        Returns:
            Dictionary containing import result and new app information
            
        Raises:
            QlikCLIError: If import fails or parameters are invalid
        """
        logger.info(f"Importing Qlik app from '{file_path}' with name '{app_name}'")
        
        # Validate file path
        if not file_path or not file_path.strip():
            raise QlikCLIError("File path cannot be empty")
        
        import_file = Path(file_path)
        if not import_file.exists():
            raise QlikCLIError(f"Import file not found: {file_path}")
        
        if not import_file.is_file():
            raise QlikCLIError(f"Import path is not a file: {file_path}")
        
        # Validate file format (basic check)
        if validate_before_import:
            file_size = import_file.stat().st_size
            
            # Check file size (basic validation)
            if file_size == 0:
                raise QlikCLIError("Import file is empty")
            
            # Check file extension
            if not import_file.suffix.lower() in ['.qvf', '.json']:
                logger.warning(f"Unexpected file extension: {import_file.suffix}. Proceeding anyway.")
            
            # Check if file is too large (>2GB warning)
            if file_size > 2 * 1024 * 1024 * 1024:
                logger.warning(f"Large file detected ({file_size / (1024*1024*1024):.1f}GB). Import may take a long time.")
        
        # Generate app name if not provided
        if not app_name:
            app_name = import_file.stem  # File name without extension
        
        # Validate app name
        if not app_name or not app_name.strip():
            raise QlikCLIError("App name cannot be empty")
        
        # Validate space if provided
        if space_id:
            try:
                spaces_result = self.space_list()
                available_spaces = [space['id'] for space in spaces_result['spaces']]
                if space_id not in available_spaces:
                    raise QlikCLIError(f"Space '{space_id}' not found or not accessible")
            except QlikCLIError as e:
                raise QlikCLIError(f"Cannot validate target space: {str(e)}")
        
        # Check for existing app with same name if not replacing
        if not replace_existing:
            try:
                search_result = self.app_search(app_name, limit=10)
                existing_apps = [app for app in search_result['apps'] 
                               if app['name'].lower() == app_name.lower()]
                
                if existing_apps:
                    # Filter by space if specified
                    if space_id:
                        existing_apps = [app for app in existing_apps if app['space_id'] == space_id]
                    
                    if existing_apps:
                        raise QlikCLIError(f"App with name '{app_name}' already exists. Use replace_existing=True to overwrite.")
            
            except QlikCLIError as e:
                if "already exists" in str(e):
                    raise e
                # If search fails for other reasons, continue with import
                logger.warning(f"Could not check for existing apps: {str(e)}")
        
        # Build import command
        cmd = self._build_base_command()
        cmd.extend(['app', 'import'])
        
        # Add file path
        cmd.extend(['--file', str(file_path)])
        
        # Add app name
        cmd.extend(['--name', app_name])
        
        # Add space if specified
        if space_id:
            cmd.extend(['--space', space_id])
        
        # Add replace flag if specified
        if replace_existing:
            cmd.append('--replace')
        
        # Track start time for duration calculation
        start_time = time.time()
        
        try:
            # Execute import command
            result = self._execute_command(cmd)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Try to get the new app ID from output
            new_app_id = None
            if result['stdout']:
                # Look for app ID in output (format may vary)
                import_output = result['stdout']
                # Try to extract app ID using common patterns
                id_patterns = [
                    r'App ID:\s*([a-f0-9-]+)',
                    r'Created app:\s*([a-f0-9-]+)',
                    r'app\s+([a-f0-9-]+)\s+created',
                    r'"id":\s*"([a-f0-9-]+)"'
                ]
                
                for pattern in id_patterns:
                    match = re.search(pattern, import_output, re.IGNORECASE)
                    if match:
                        new_app_id = match.group(1)
                        break
            
            # Verify import by searching for the app
            verification_result = None
            if new_app_id:
                try:
                    verification_result = self.app_get(new_app_id)
                except Exception:
                    logger.warning(f"Could not verify imported app with ID: {new_app_id}")
            else:
                # Try to find by name
                try:
                    search_result = self.app_search(app_name, limit=5)
                    matching_apps = [app for app in search_result['apps'] 
                                   if app['name'] == app_name]
                    if matching_apps:
                        new_app_id = matching_apps[0]['id']
                        verification_result = self.app_get(new_app_id)
                except Exception:
                    logger.warning(f"Could not verify imported app by name: {app_name}")
            
            logger.info(f"Successfully imported app '{app_name}' from '{file_path}' (ID: {new_app_id}, {duration:.2f}s)")
            
            return {
                'success': True,
                'file_path': str(file_path),
                'app_name': app_name,
                'new_app_id': new_app_id,
                'space_id': space_id,
                'replaced_existing': replace_existing,
                'import_duration_seconds': round(duration, 2),
                'verification_result': verification_result,
                'command_result': result
            }
            
        except QlikCLIError as e:
            error_msg = f"Failed to import app from '{file_path}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during app import: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    def app_copy(self,
                 source_app_id: str,
                 target_name: str,
                 target_space_id: Optional[str] = None,
                 include_data: bool = True,
                 copy_permissions: bool = False) -> Dict[str, Any]:
        """
        Copy existing Qlik application within the same tenant
        
        Args:
            source_app_id: Source app ID to copy from
            target_name: Name for the copied app
            target_space_id: Target space ID (optional, uses source app space if not provided)
            include_data: Whether to include data in the copy (default: True)
            copy_permissions: Whether to copy permissions (default: False)
            
        Returns:
            Dictionary containing copy result and new app information
            
        Raises:
            QlikCLIError: If copy fails or parameters are invalid
        """
        logger.info(f"Copying Qlik app '{source_app_id}' to new app '{target_name}'")
        
        # Validate parameters
        if not source_app_id or not source_app_id.strip():
            raise QlikCLIError("Source app ID cannot be empty")
        
        if not target_name or not target_name.strip():
            raise QlikCLIError("Target app name cannot be empty")
        
        # Validate source app exists and get details
        try:
            source_app_details = self.app_get(source_app_id)
            if not source_app_details['success']:
                raise QlikCLIError(f"Source app '{source_app_id}' not found or not accessible")
            
            source_app = source_app_details['app']
            logger.info(f"Source app found: '{source_app['name']}' in space '{source_app['space']['name']}'")
            
        except QlikCLIError as e:
            raise QlikCLIError(f"Cannot validate source app: {str(e)}")
        
        # Use source app space if target space not specified
        if not target_space_id:
            target_space_id = source_app['space']['id']
            logger.info(f"Using source app space as target: {target_space_id}")
        
        # Validate target space if specified
        if target_space_id:
            try:
                spaces_result = self.space_list()
                available_spaces = [space['id'] for space in spaces_result['spaces']]
                if target_space_id not in available_spaces:
                    raise QlikCLIError(f"Target space '{target_space_id}' not found or not accessible")
            except QlikCLIError as e:
                raise QlikCLIError(f"Cannot validate target space: {str(e)}")
        
        # Check for existing app with same name in target space
        try:
            search_result = self.app_search(target_name, limit=10)
            existing_apps = [app for app in search_result['apps'] 
                           if app['name'].lower() == target_name.lower()]
            
            if existing_apps and target_space_id:
                existing_apps = [app for app in existing_apps if app['space_id'] == target_space_id]
            
            if existing_apps:
                raise QlikCLIError(f"App with name '{target_name}' already exists in target space")
        
        except QlikCLIError as e:
            if "already exists" in str(e):
                raise e
            # If search fails for other reasons, continue with copy
            logger.warning(f"Could not check for existing apps: {str(e)}")
        
        # Build copy command
        cmd = self._build_base_command()
        cmd.extend(['app', 'copy'])
        
        # Add source app ID
        cmd.extend(['--app', source_app_id])
        
        # Add target name
        cmd.extend(['--name', target_name])
        
        # Add target space if specified
        if target_space_id:
            cmd.extend(['--space', target_space_id])
        
        # Add data option
        if not include_data:
            cmd.append('--no-data')
        
        # Add permissions option (if supported by qlik-cli)
        if copy_permissions:
            cmd.append('--copy-permissions')
        
        # Track start time for duration calculation
        start_time = time.time()
        
        try:
            # Execute copy command
            result = self._execute_command(cmd)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Try to get the new app ID from output
            new_app_id = None
            if result['stdout']:
                # Look for app ID in output (format may vary)
                copy_output = result['stdout']
                # Try to extract app ID using common patterns
                id_patterns = [
                    r'App ID:\s*([a-f0-9-]+)',
                    r'Copied to:\s*([a-f0-9-]+)',
                    r'app\s+([a-f0-9-]+)\s+created',
                    r'"id":\s*"([a-f0-9-]+)"'
                ]
                
                for pattern in id_patterns:
                    match = re.search(pattern, copy_output, re.IGNORECASE)
                    if match:
                        new_app_id = match.group(1)
                        break
            
            # Verify copy by searching for the app
            verification_result = None
            if new_app_id:
                try:
                    verification_result = self.app_get(new_app_id)
                except Exception:
                    logger.warning(f"Could not verify copied app with ID: {new_app_id}")
            else:
                # Try to find by name in target space
                try:
                    search_result = self.app_search(target_name, limit=5)
                    matching_apps = [app for app in search_result['apps'] 
                                   if app['name'] == target_name and app['space_id'] == target_space_id]
                    if matching_apps:
                        new_app_id = matching_apps[0]['id']
                        verification_result = self.app_get(new_app_id)
                except Exception:
                    logger.warning(f"Could not verify copied app by name: {target_name}")
            
            logger.info(f"Successfully copied app '{source_app_id}' to '{target_name}' (ID: {new_app_id}, {duration:.2f}s)")
            
            return {
                'success': True,
                'source_app_id': source_app_id,
                'source_app_name': source_app['name'],
                'target_name': target_name,
                'new_app_id': new_app_id,
                'target_space_id': target_space_id,
                'include_data': include_data,
                'copy_permissions': copy_permissions,
                'copy_duration_seconds': round(duration, 2),
                'verification_result': verification_result,
                'command_result': result
            }
            
        except QlikCLIError as e:
            error_msg = f"Failed to copy app '{source_app_id}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during app copy: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    def app_publish(self,
                    app_id: str,
                    target_space_id: str,
                    publish_name: Optional[str] = None,
                    replace_existing: bool = False) -> Dict[str, Any]:
        """
        Publish Qlik application to managed space for broader access
        
        Args:
            app_id: App ID to publish
            target_space_id: Managed space ID to publish to
            publish_name: Name for published app (optional, uses original name if not provided)
            replace_existing: Whether to replace existing published app
            
        Returns:
            Dictionary containing publication result and published app information
            
        Raises:
            QlikCLIError: If publication fails or parameters are invalid
        """
        logger.info(f"Publishing Qlik app '{app_id}' to managed space '{target_space_id}'")
        
        # Validate parameters
        if not app_id or not app_id.strip():
            raise QlikCLIError("App ID cannot be empty")
        
        if not target_space_id or not target_space_id.strip():
            raise QlikCLIError("Target space ID cannot be empty")
        
        # Validate source app exists and get details
        try:
            source_app_details = self.app_get(app_id)
            if not source_app_details['success']:
                raise QlikCLIError(f"App '{app_id}' not found or not accessible")
            
            source_app = source_app_details['app']
            logger.info(f"Source app found: '{source_app['name']}' in space '{source_app['space']['name']}'")
            
        except QlikCLIError as e:
            raise QlikCLIError(f"Cannot validate source app: {str(e)}")
        
        # Use source app name if publish name not specified
        if not publish_name:
            publish_name = source_app['name']
            logger.info(f"Using source app name for publication: {publish_name}")
        
        # Validate target space exists and is managed
        try:
            spaces_result = self.space_list()
            target_space = None
            for space in spaces_result['spaces']:
                if space['id'] == target_space_id:
                    target_space = space
                    break
            
            if not target_space:
                raise QlikCLIError(f"Target space '{target_space_id}' not found")
            
            if target_space['type'].lower() != 'managed':
                logger.warning(f"Target space '{target_space['name']}' is not a managed space (type: {target_space['type']})")
            
        except QlikCLIError as e:
            raise QlikCLIError(f"Cannot validate target space: {str(e)}")
        
        # Check for existing published app with same name if not replacing
        if not replace_existing:
            try:
                search_result = self.app_search(publish_name, limit=10)
                existing_apps = [app for app in search_result['apps'] 
                               if app['name'].lower() == publish_name.lower() and 
                                  app['space_id'] == target_space_id]
                
                if existing_apps:
                    raise QlikCLIError(f"App with name '{publish_name}' already exists in target space. Use replace_existing=True to overwrite.")
            
            except QlikCLIError as e:
                if "already exists" in str(e):
                    raise e
                # If search fails for other reasons, continue with publication
                logger.warning(f"Could not check for existing published apps: {str(e)}")
        
        # Build publish command
        cmd = self._build_base_command()
        cmd.extend(['app', 'publish'])
        
        # Add app ID
        cmd.extend(['--app', app_id])
        
        # Add target space
        cmd.extend(['--space', target_space_id])
        
        # Add publish name if different from original
        if publish_name != source_app['name']:
            cmd.extend(['--name', publish_name])
        
        # Add replace flag if specified
        if replace_existing:
            cmd.append('--replace')
        
        # Track start time for duration calculation
        start_time = time.time()
        
        try:
            # Execute publish command
            result = self._execute_command(cmd)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Try to get the published app ID from output
            published_app_id = None
            if result['stdout']:
                # Look for app ID in output (format may vary)
                publish_output = result['stdout']
                # Try to extract app ID using common patterns
                id_patterns = [
                    r'Published app ID:\s*([a-f0-9-]+)',
                    r'Published to:\s*([a-f0-9-]+)',
                    r'app\s+([a-f0-9-]+)\s+published',
                    r'"id":\s*"([a-f0-9-]+)"'
                ]
                
                for pattern in id_patterns:
                    match = re.search(pattern, publish_output, re.IGNORECASE)
                    if match:
                        published_app_id = match.group(1)
                        break
            
            # Verify publication by searching for the app in target space
            verification_result = None
            if published_app_id:
                try:
                    verification_result = self.app_get(published_app_id)
                except Exception:
                    logger.warning(f"Could not verify published app with ID: {published_app_id}")
            else:
                # Try to find by name in target space
                try:
                    search_result = self.app_search(publish_name, limit=5)
                    matching_apps = [app for app in search_result['apps'] 
                                   if app['name'] == publish_name and app['space_id'] == target_space_id]
                    if matching_apps:
                        published_app_id = matching_apps[0]['id']
                        verification_result = self.app_get(published_app_id)
                except Exception:
                    logger.warning(f"Could not verify published app by name: {publish_name}")
            
            logger.info(f"Successfully published app '{app_id}' to space '{target_space_id}' (Published ID: {published_app_id}, {duration:.2f}s)")
            
            return {
                'success': True,
                'source_app_id': app_id,
                'source_app_name': source_app['name'],
                'published_app_id': published_app_id,
                'publish_name': publish_name,
                'target_space_id': target_space_id,
                'target_space_name': target_space['name'],
                'replaced_existing': replace_existing,
                'publish_duration_seconds': round(duration, 2),
                'verification_result': verification_result,
                'command_result': result
            }
            
        except QlikCLIError as e:
            error_msg = f"Failed to publish app '{app_id}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error during app publication: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)