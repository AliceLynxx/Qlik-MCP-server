"""
Qlik CLI Integration Module

This module provides a Python interface to qlik-cli commands,
specifically focusing on app build and unbuild operations.
"""

import subprocess
import json
import logging
import os
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from config import Config

# Configure logging
logger = logging.getLogger(__name__)


class QlikCLIError(Exception):
    """Custom exception for Qlik CLI related errors"""
    pass


class QlikCLI:
    """
    Python interface to qlik-cli commands
    
    This class provides methods to execute qlik-cli commands with proper
    error handling, logging, and parameter validation.
    """
    
    def __init__(self, config: Config):
        """
        Initialize QlikCLI with configuration
        
        Args:
            config: Configuration object containing qlik-cli settings
        """
        self.config = config
        self.cli_path = config.qlik.cli_path
        self.timeout = config.qlik.command_timeout
        
        # Validate qlik-cli is available
        if not self._validate_cli_available():
            raise QlikCLIError(f"qlik-cli not found at path: {self.cli_path}")
    
    def _validate_cli_available(self) -> bool:
        """Check if qlik-cli is available and working"""
        try:
            result = subprocess.run(
                [self.cli_path, 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def _validate_file_path(self, path: str) -> bool:
        """
        Validate that a file path exists and is readable
        
        Args:
            path: File path to validate
            
        Returns:
            True if file exists and is readable, False otherwise
        """
        try:
            file_path = Path(path)
            return file_path.exists() and file_path.is_file()
        except (OSError, ValueError):
            return False
    
    def _validate_directory_path(self, path: str) -> bool:
        """
        Validate that a directory path exists or can be created
        
        Args:
            path: Directory path to validate
            
        Returns:
            True if directory exists or can be created, False otherwise
        """
        try:
            dir_path = Path(path)
            if dir_path.exists():
                return dir_path.is_dir()
            # Check if parent directory exists and is writable
            parent = dir_path.parent
            return parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)
        except (OSError, ValueError):
            return False
    
    def _build_base_command(self) -> List[str]:
        """
        Build base qlik-cli command with global flags
        
        Returns:
            List of command components
        """
        cmd = [self.cli_path]
        
        # Add global flags from config if available
        if self.config.qlik.tenant_url:
            cmd.extend(['--server', self.config.qlik.tenant_url])
        
        if self.config.server.debug:
            cmd.append('--verbose')
        
        return cmd
    
    def _execute_command(self, command: List[str]) -> Dict[str, Any]:
        """
        Execute qlik-cli command with proper error handling
        
        Args:
            command: List of command components
            
        Returns:
            Dictionary containing command result
            
        Raises:
            QlikCLIError: If command execution fails
        """
        logger.info(f"Executing qlik-cli command: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=os.environ.copy()
            )
            
            logger.debug(f"Command return code: {result.returncode}")
            logger.debug(f"Command stdout: {result.stdout}")
            logger.debug(f"Command stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = f"qlik-cli command failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                raise QlikCLIError(error_msg)
            
            return {
                'success': True,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(command)
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"qlik-cli command timed out after {self.timeout} seconds"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except FileNotFoundError:
            error_msg = f"qlik-cli executable not found: {self.cli_path}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error executing qlik-cli command: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
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
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['app', 'unbuild'])
        
        # Add app parameter
        cmd.extend(['--app', app])
        
        # Validate and add directory parameter
        if dir:
            if not self._validate_directory_path(dir):
                raise QlikCLIError(f"Invalid or inaccessible directory: {dir}")
            cmd.extend(['--dir', dir])
        
        # Add boolean flags
        if no_data:
            cmd.append('--no-data')
        
        # Execute command
        return self._execute_command(cmd)
    
    def get_cli_version(self) -> Dict[str, Any]:
        """
        Get qlik-cli version information
        
        Returns:
            Dictionary containing version information
        """
        cmd = [self.cli_path, '--version']
        return self._execute_command(cmd)
    
    def validate_connection(self) -> bool:
        """
        Validate connection to Qlik Cloud
        
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            # Try to execute a simple command to test connectivity
            cmd = self._build_base_command()
            cmd.extend(['--help'])
            result = self._execute_command(cmd)
            return result['success']
        except QlikCLIError:
            return False