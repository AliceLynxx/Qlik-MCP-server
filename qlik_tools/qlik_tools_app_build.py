"""
Qlik App Build Tools

This module provides methods for app build and unbuild operations.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .qlik_cli_base import QlikCLI, QlikCLIError

# Configure logging
logger = logging.getLogger(__name__)


class QlikAppBuildMixin:
    """Mixin class for app build operations"""
    
    def app_build(self, 
                  app: str,
                  connections: Optional[str] = None,
                  script: Optional[str] = None,
                  dimensions: Optional[Union[str, List[str]]] = None,
                  measures: Optional[Union[str, List[str]]] = None,
                  objects: Optional[Union[str, List[str]]] = None,
                  variables: Optional[Union[str, List[str]]] = None,
                  bookmarks: Optional[Union[str, List[str]]] = None,
                  app_properties: Optional[str] = None,
                  limit: Optional[int] = None,
                  no_data: bool = False,
                  no_reload: bool = False,
                  no_save: bool = False,
                  silent: bool = False,
                  **kwargs) -> Dict[str, Any]:
        """
        Execute qlik app build command
        
        Args:
            app: Name or identifier of the app
            connections: Path to a yml file containing data connection definitions
            script: Path to a qvs file containing the app data reload script
            dimensions: A list of generic dimension json paths (string or list)
            measures: A list of generic measures json paths (string or list)
            objects: A list of generic object json paths (string or list)
            variables: A list of generic variable json paths (string or list)
            bookmarks: A list of generic bookmark json paths (string or list)
            app_properties: Path to a json file containing the app properties
            limit: Limit the number of rows to load
            no_data: Open app without data
            no_reload: Do not run the reload script
            no_save: Do not save the app
            silent: Do not log reload output
            **kwargs: Additional parameters
            
        Returns:
            Dictionary containing command result
            
        Raises:
            QlikCLIError: If command execution fails or parameters are invalid
        """
        logger.info(f"Building Qlik app: {app}")
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['app', 'build'])
        
        # Add app parameter
        cmd.extend(['--app', app])
        
        # Validate and add file-based parameters
        if connections:
            if not self._validate_file_path(connections):
                raise QlikCLIError(f"Connections file not found: {connections}")
            cmd.extend(['--connections', connections])
        
        if script:
            if not self._validate_file_path(script):
                raise QlikCLIError(f"Script file not found: {script}")
            cmd.extend(['--script', script])
        
        if app_properties:
            if not self._validate_file_path(app_properties):
                raise QlikCLIError(f"App properties file not found: {app_properties}")
            cmd.extend(['--app-properties', app_properties])
        
        # Handle list parameters (dimensions, measures, objects, variables, bookmarks)
        def add_list_parameter(param_name: str, param_value: Union[str, List[str], None]):
            if param_value:
                if isinstance(param_value, str):
                    # Single file path
                    if not self._validate_file_path(param_value):
                        raise QlikCLIError(f"{param_name.capitalize()} file not found: {param_value}")
                    cmd.extend([f'--{param_name}', param_value])
                elif isinstance(param_value, list):
                    # Multiple file paths
                    for file_path in param_value:
                        if not self._validate_file_path(file_path):
                            raise QlikCLIError(f"{param_name.capitalize()} file not found: {file_path}")
                        cmd.extend([f'--{param_name}', file_path])
        
        add_list_parameter('dimensions', dimensions)
        add_list_parameter('measures', measures)
        add_list_parameter('objects', objects)
        add_list_parameter('variables', variables)
        add_list_parameter('bookmarks', bookmarks)
        
        # Add numeric parameters
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise QlikCLIError(f"Limit must be a non-negative integer: {limit}")
            cmd.extend(['--limit', str(limit)])
        
        # Add boolean flags
        if no_data:
            cmd.append('--no-data')
        if no_reload:
            cmd.append('--no-reload')
        if no_save:
            cmd.append('--no-save')
        if silent:
            cmd.append('--silent')
        
        # Execute command
        return self._execute_command(cmd)
    
    def app_unbuild(self,
                    app: str,
                    dir: Optional[str] = None,
                    no_data: bool = False,
                    **kwargs) -> Dict[str, Any]:
        """
        Execute qlik app unbuild command
        
        Args:
            app: Name or identifier of the app
            dir: Path to the folder where the unbuilt app is exported
            no_data: Open app without data
            **kwargs: Additional parameters
            
        Returns:
            Dictionary containing command result
            
        Raises:
            QlikCLIError: If command execution fails or parameters are invalid
        """
        logger.info(f"Unbuilding Qlik app: {app}")
        
        # Determine the target directory
        target_dir = self._determine_unbuild_directory(dir)
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['app', 'unbuild'])
        
        # Add app parameter
        cmd.extend(['--app', app])
        
        # Add directory parameter if specified
        if target_dir:
            # Ensure directory exists
            self._ensure_directory_exists(target_dir)
            cmd.extend(['--dir', target_dir])
        
        # Add boolean flags
        if no_data:
            cmd.append('--no-data')
        
        # Execute command
        result = self._execute_command(cmd)
        
        # Add directory information to result if available
        if target_dir:
            result['unbuild_directory'] = target_dir
            logger.info(f"App unbuilt to directory: {target_dir}")
        
        return result
    
    def _determine_unbuild_directory(self, explicit_dir: Optional[str]) -> Optional[str]:
        """
        Determine the target directory for unbuild operation
        
        Args:
            explicit_dir: Explicitly specified directory
            
        Returns:
            Target directory path or None if no directory should be used
        """
        # Explicit directory has highest priority
        if explicit_dir:
            return explicit_dir
        
        # Check for default directory from configuration
        if hasattr(self.config.qlik, 'get_unbuild_directory'):
            default_dir = self.config.qlik.get_unbuild_directory()
            if default_dir:
                return default_dir
        
        # Fallback to environment variable
        env_dir = os.getenv('QLIK_DEFAULT_UNBUILD_DIRECTORY')
        if env_dir:
            return env_dir
        
        # No directory specified, let qlik-cli use its default behavior
        return None
    
    def _ensure_directory_exists(self, directory: str) -> None:
        """
        Ensure that the specified directory exists, creating it if necessary
        
        Args:
            directory: Directory path to ensure exists
            
        Raises:
            QlikCLIError: If directory cannot be created or accessed
        """
        try:
            dir_path = Path(directory)
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Verify directory is writable
            if not os.access(dir_path, os.W_OK):
                raise QlikCLIError(f"Directory is not writable: {directory}")
                
        except OSError as e:
            raise QlikCLIError(f"Failed to create or access directory '{directory}': {e}")