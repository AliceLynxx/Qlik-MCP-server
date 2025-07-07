"""
Qlik CLI Base Module

This module provides the base QlikCLI class with core functionality,
error handling, validation methods, and command execution infrastructure.
"""

import subprocess
import json
import logging
import os
import re
import shutil
import tempfile
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from urllib.parse import urlparse

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
    error handling, logging, and parameter validation. It includes context
    management for multi-tenant authentication, app discovery functionality,
    and secure credential handling.
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
    
    def _validate_tenant_url(self, tenant_url: str) -> bool:
        """
        Validate Qlik Cloud tenant URL format
        
        Args:
            tenant_url: Tenant URL to validate
            
        Returns:
            True if URL format is valid, False otherwise
        """
        try:
            parsed = urlparse(tenant_url)
            # Check if it's a valid URL with https scheme
            if parsed.scheme != 'https':
                return False
            # Check if it looks like a Qlik Cloud URL
            if not parsed.netloc:
                return False
            # Basic pattern check for Qlik Cloud domains
            qlik_patterns = [
                r'.*\.qlikcloud\.com$',
                r'.*\.us\.qlikcloud\.com$',
                r'.*\.eu\.qlikcloud\.com$',
                r'.*\.ap\.qlikcloud\.com$'
            ]
            return any(re.match(pattern, parsed.netloc) for pattern in qlik_patterns)
        except Exception:
            return False
    
    def _ensure_directory_exists(self, path: str) -> bool:
        """
        Ensure directory exists, create if necessary
        
        Args:
            path: Directory path to ensure exists
            
        Returns:
            True if directory exists or was created successfully
        """
        try:
            dir_path = Path(path)
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, PermissionError) as e:
            logger.error(f"Failed to create directory {path}: {str(e)}")
            return False
    
    def _get_available_disk_space(self, path: str) -> int:
        """
        Get available disk space in bytes for given path
        
        Args:
            path: Path to check disk space for
            
        Returns:
            Available disk space in bytes, -1 if unable to determine
        """
        try:
            statvfs = os.statvfs(path)
            return statvfs.f_frsize * statvfs.f_bavail
        except (OSError, AttributeError):
            # Fallback for Windows
            try:
                import shutil
                total, used, free = shutil.disk_usage(path)
                return free
            except Exception:
                return -1
    
    def _validate_export_format(self, format_type: str) -> bool:
        """
        Validate export format
        
        Args:
            format_type: Format to validate
            
        Returns:
            True if format is valid
        """
        valid_formats = ['qvf', 'json', 'xlsx']
        return format_type.lower() in valid_formats
    
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
    
    def _execute_command(self, command: List[str], mask_sensitive: bool = False) -> Dict[str, Any]:
        """
        Execute qlik-cli command with proper error handling
        
        Args:
            command: List of command components
            mask_sensitive: Whether to mask sensitive information in logs
            
        Returns:
            Dictionary containing command result
            
        Raises:
            QlikCLIError: If command execution fails
        """
        # Create masked command for logging if needed
        log_command = command.copy()
        if mask_sensitive:
            # Mask API keys and other sensitive data
            for i, arg in enumerate(log_command):
                if i > 0 and log_command[i-1] in ['--api-key', '--token']:
                    log_command[i] = '***MASKED***'
        
        logger.info(f"Executing qlik-cli command: {' '.join(log_command)}")
        
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
            if result.stderr and not mask_sensitive:
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
                'command': ' '.join(log_command)
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
    
    def _parse_json_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse JSON output from qlik-cli commands
        
        Args:
            output: Raw JSON output string
            
        Returns:
            List of parsed JSON objects
            
        Raises:
            QlikCLIError: If JSON parsing fails
        """
        if not output or not output.strip():
            return []
        
        try:
            # Try to parse as single JSON object first
            try:
                parsed = json.loads(output.strip())
                return [parsed] if isinstance(parsed, dict) else parsed
            except json.JSONDecodeError:
                # Try to parse as multiple JSON objects (one per line)
                objects = []
                for line in output.strip().split('\n'):
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            objects.append(obj)
                        except json.JSONDecodeError:
                            # Skip invalid JSON lines
                            continue
                return objects
        except Exception as e:
            logger.warning(f"Failed to parse JSON output: {str(e)}")
            raise QlikCLIError(f"Failed to parse command output as JSON: {str(e)}")
    
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
    
    def validate_api_key(self, api_key: str, tenant_url: str) -> bool:
        """
        Validate API key against a Qlik Cloud tenant
        
        Args:
            api_key: API key to validate
            tenant_url: Tenant URL to validate against
            
        Returns:
            True if API key is valid, False otherwise
        """
        logger.info(f"Validating API key against tenant: {tenant_url}")
        
        try:
            # Build a simple command to test authentication
            cmd = [self.cli_path, '--server', tenant_url, '--api-key', api_key, 'user', 'me']
            
            # Execute command with sensitive data masking
            result = self._execute_command(cmd, mask_sensitive=True)
            
            # If command succeeds, API key is valid
            logger.info("API key validation successful")
            return True
            
        except QlikCLIError as e:
            logger.warning(f"API key validation failed: {str(e)}")
            return False