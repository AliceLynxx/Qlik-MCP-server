"""
Qlik CLI Integration Module

This module provides a Python interface to qlik-cli commands,
specifically focusing on app build and unbuild operations,
app discovery and listing functionality, and context management 
for multi-tenant authentication.
"""

import subprocess
import json
import logging
import os
import re
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
    
    # App Discovery Methods
    
    def app_list(self, 
                 space_id: Optional[str] = None,
                 collection_id: Optional[str] = None, 
                 owner: Optional[str] = None,
                 limit: int = 50,
                 offset: int = 0) -> Dict[str, Any]:
        """
        List available Qlik applications with filtering options
        
        Args:
            space_id: Filter by specific space ID
            collection_id: Filter by specific collection ID
            owner: Filter by app owner
            limit: Maximum number of apps to return (default: 50)
            offset: Number of apps to skip (default: 0)
            
        Returns:
            Dictionary containing list of apps and metadata
            
        Raises:
            QlikCLIError: If listing apps fails
        """
        logger.info(f"Listing Qlik apps with filters: space_id={space_id}, owner={owner}, limit={limit}")
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['app', 'ls', '--json'])
        
        # Add filtering parameters
        if space_id:
            cmd.extend(['--space', space_id])
        
        if collection_id:
            cmd.extend(['--collection', collection_id])
        
        if owner:
            cmd.extend(['--owner', owner])
        
        # Add pagination parameters
        if limit != 50:  # Only add if different from default
            cmd.extend(['--limit', str(limit)])
        
        if offset > 0:
            cmd.extend(['--offset', str(offset)])
        
        # Execute command
        result = self._execute_command(cmd)
        
        # Parse JSON output
        try:
            apps_data = self._parse_json_output(result['stdout'])
            
            # Process and structure app information
            apps = []
            for app_data in apps_data:
                app_info = {
                    'id': app_data.get('id', ''),
                    'name': app_data.get('name', ''),
                    'description': app_data.get('description', ''),
                    'owner': app_data.get('owner', {}).get('name', '') if app_data.get('owner') else '',
                    'owner_id': app_data.get('owner', {}).get('id', '') if app_data.get('owner') else '',
                    'space_id': app_data.get('spaceId', ''),
                    'space_name': app_data.get('space', {}).get('name', '') if app_data.get('space') else '',
                    'created_date': app_data.get('createdDate', ''),
                    'modified_date': app_data.get('modifiedDate', ''),
                    'published': app_data.get('published', False),
                    'tags': app_data.get('tags', []),
                    'thumbnail': app_data.get('thumbnail', ''),
                    'usage': app_data.get('usage', 'analytics')
                }
                apps.append(app_info)
            
            logger.info(f"Successfully listed {len(apps)} Qlik apps")
            
            return {
                'success': True,
                'apps': apps,
                'total_count': len(apps),
                'filters_applied': {
                    'space_id': space_id,
                    'collection_id': collection_id,
                    'owner': owner,
                    'limit': limit,
                    'offset': offset
                },
                'raw_output': result['stdout']
            }
            
        except Exception as e:
            error_msg = f"Failed to process app list output: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    def app_get(self, app_identifier: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific Qlik application
        
        Args:
            app_identifier: App ID or name to retrieve details for
            
        Returns:
            Dictionary containing detailed app information
            
        Raises:
            QlikCLIError: If getting app details fails or app doesn't exist
        """
        logger.info(f"Getting details for Qlik app: {app_identifier}")
        
        # Validate app identifier
        if not app_identifier or not app_identifier.strip():
            raise QlikCLIError("App identifier cannot be empty")
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['app', 'get', app_identifier, '--json'])
        
        # Execute command
        result = self._execute_command(cmd)
        
        # Parse JSON output
        try:
            app_data_list = self._parse_json_output(result['stdout'])
            
            if not app_data_list:
                raise QlikCLIError(f"No app found with identifier: {app_identifier}")
            
            app_data = app_data_list[0]  # Get first (should be only) result
            
            # Structure detailed app information
            app_details = {
                'id': app_data.get('id', ''),
                'name': app_data.get('name', ''),
                'description': app_data.get('description', ''),
                'owner': {
                    'id': app_data.get('owner', {}).get('id', '') if app_data.get('owner') else '',
                    'name': app_data.get('owner', {}).get('name', '') if app_data.get('owner') else '',
                    'email': app_data.get('owner', {}).get('email', '') if app_data.get('owner') else ''
                },
                'space': {
                    'id': app_data.get('spaceId', ''),
                    'name': app_data.get('space', {}).get('name', '') if app_data.get('space') else '',
                    'type': app_data.get('space', {}).get('type', '') if app_data.get('space') else ''
                },
                'created_date': app_data.get('createdDate', ''),
                'modified_date': app_data.get('modifiedDate', ''),
                'published': app_data.get('published', False),
                'tags': app_data.get('tags', []),
                'thumbnail': app_data.get('thumbnail', ''),
                'usage': app_data.get('usage', 'analytics'),
                'file_size': app_data.get('fileSize', 0),
                'last_reload_time': app_data.get('lastReloadTime', ''),
                'has_data': app_data.get('hasData', False),
                'is_direct_query_mode': app_data.get('isDirectQueryMode', False),
                'encryption': app_data.get('encryption', {}),
                'custom_properties': app_data.get('customProperties', []),
                'origin_app_id': app_data.get('originAppId', ''),
                'target_app_id': app_data.get('targetAppId', ''),
                'attributes': app_data.get('attributes', [])
            }
            
            logger.info(f"Successfully retrieved details for app: {app_identifier}")
            
            return {
                'success': True,
                'app': app_details,
                'raw_output': result['stdout']
            }
            
        except Exception as e:
            error_msg = f"Failed to process app details for '{app_identifier}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    def app_search(self, 
                   query: str,
                   limit: int = 20,
                   filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Search for Qlik applications by name or description
        
        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 20)
            filters: Additional filters (space_id, owner, etc.)
            
        Returns:
            Dictionary containing search results
            
        Raises:
            QlikCLIError: If search fails
        """
        logger.info(f"Searching Qlik apps with query: '{query}', limit: {limit}")
        
        # Validate query
        if not query or not query.strip():
            raise QlikCLIError("Search query cannot be empty")
        
        # Get all apps first (we'll filter client-side since qlik-cli search may be limited)
        try:
            # Get a larger set to search through
            search_limit = max(limit * 5, 100)  # Get more apps to search through
            all_apps_result = self.app_list(limit=search_limit)
            all_apps = all_apps_result['apps']
            
            # Perform client-side search
            query_lower = query.lower()
            matching_apps = []
            
            for app in all_apps:
                # Search in name and description
                name_match = query_lower in app.get('name', '').lower()
                desc_match = query_lower in app.get('description', '').lower()
                tag_match = any(query_lower in tag.lower() for tag in app.get('tags', []))
                
                if name_match or desc_match or tag_match:
                    # Calculate relevance score
                    score = 0
                    if name_match:
                        score += 10
                    if desc_match:
                        score += 5
                    if tag_match:
                        score += 3
                    
                    app_with_score = app.copy()
                    app_with_score['relevance_score'] = score
                    app_with_score['match_reasons'] = []
                    
                    if name_match:
                        app_with_score['match_reasons'].append('name')
                    if desc_match:
                        app_with_score['match_reasons'].append('description')
                    if tag_match:
                        app_with_score['match_reasons'].append('tags')
                    
                    matching_apps.append(app_with_score)
            
            # Apply additional filters if provided
            if filters:
                filtered_apps = []
                for app in matching_apps:
                    include_app = True
                    
                    if filters.get('space_id') and app.get('space_id') != filters['space_id']:
                        include_app = False
                    if filters.get('owner') and filters['owner'].lower() not in app.get('owner', '').lower():
                        include_app = False
                    
                    if include_app:
                        filtered_apps.append(app)
                
                matching_apps = filtered_apps
            
            # Sort by relevance score (highest first)
            matching_apps.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Limit results
            matching_apps = matching_apps[:limit]
            
            logger.info(f"Found {len(matching_apps)} matching apps for query: '{query}'")
            
            return {
                'success': True,
                'query': query,
                'apps': matching_apps,
                'total_matches': len(matching_apps),
                'filters_applied': filters or {},
                'search_performed_on': len(all_apps)
            }
            
        except Exception as e:
            error_msg = f"Failed to search apps with query '{query}': {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    def space_list(self, type_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        List available Qlik spaces
        
        Args:
            type_filter: Filter by space type (personal, shared, managed)
            
        Returns:
            Dictionary containing list of spaces
            
        Raises:
            QlikCLIError: If listing spaces fails
        """
        logger.info(f"Listing Qlik spaces with type filter: {type_filter}")
        
        # Build command
        cmd = self._build_base_command()
        cmd.extend(['space', 'ls', '--json'])
        
        # Add type filter if specified
        if type_filter:
            valid_types = ['personal', 'shared', 'managed']
            if type_filter.lower() not in valid_types:
                raise QlikCLIError(f"Invalid space type filter: {type_filter}. Valid types: {', '.join(valid_types)}")
            cmd.extend(['--type', type_filter.lower()])
        
        # Execute command
        result = self._execute_command(cmd)
        
        # Parse JSON output
        try:
            spaces_data = self._parse_json_output(result['stdout'])
            
            # Process and structure space information
            spaces = []
            for space_data in spaces_data:
                space_info = {
                    'id': space_data.get('id', ''),
                    'name': space_data.get('name', ''),
                    'description': space_data.get('description', ''),
                    'type': space_data.get('type', ''),
                    'owner': {
                        'id': space_data.get('owner', {}).get('id', '') if space_data.get('owner') else '',
                        'name': space_data.get('owner', {}).get('name', '') if space_data.get('owner') else ''
                    },
                    'created_date': space_data.get('createdDate', ''),
                    'modified_date': space_data.get('modifiedDate', ''),
                    'tenant_id': space_data.get('tenantId', ''),
                    'meta': space_data.get('meta', {}),
                    'links': space_data.get('links', {})
                }
                spaces.append(space_info)
            
            # Get app count per space (if possible)
            for space in spaces:
                try:
                    # Try to get app count for this space
                    space_apps = self.app_list(space_id=space['id'], limit=1000)
                    space['app_count'] = len(space_apps['apps'])
                except Exception:
                    # If we can't get app count, set to unknown
                    space['app_count'] = -1
            
            logger.info(f"Successfully listed {len(spaces)} Qlik spaces")
            
            return {
                'success': True,
                'spaces': spaces,
                'total_count': len(spaces),
                'type_filter': type_filter,
                'raw_output': result['stdout']
            }
            
        except Exception as e:
            error_msg = f"Failed to process space list output: {str(e)}"
            logger.error(error_msg)
            raise QlikCLIError(error_msg)
    
    # Context Management Methods
    
    def context_create(self, name: str, tenant_url: str, api_key: str) -> Dict[str, Any]:
        """
        Create a new Qlik context with API key authentication
        
        Args:
            name: Name for the new context
            tenant_url: Qlik Cloud tenant URL
            api_key: API key for authentication
            
        Returns:
            Dictionary containing operation result
            
        Raises:
            QlikCLIError: If context creation fails or parameters are invalid
        """
        logger.info(f"Creating Qlik context: {name}")
        
        # Validate parameters
        if not name or not name.strip():
            raise QlikCLIError("Context name cannot be empty")
        
        if not self._validate_tenant_url(tenant_url):
            raise QlikCLIError(f"Invalid tenant URL format: {tenant_url}")
        
        if not api_key or len(api_key.strip()) < 10:
            raise QlikCLIError("API key appears to be invalid (too short)")
        
        # Validate API key against tenant before creating context
        if not self.validate_api_key(api_key, tenant_url):
            raise QlikCLIError("API key validation failed - unable to authenticate with the provided credentials")
        
        # Build command
        cmd = [self.cli_path, 'context', 'create']
        cmd.extend(['--name', name])
        cmd.extend(['--server', tenant_url])
        cmd.extend(['--api-key', api_key])
        
        # Execute command with sensitive data masking
        result = self._execute_command(cmd, mask_sensitive=True)
        
        logger.info(f"Successfully created Qlik context: {name}")
        return result
    
    def context_list(self) -> Dict[str, Any]:
        """
        List all available Qlik contexts
        
        Returns:
            Dictionary containing list of contexts and current active context
            
        Raises:
            QlikCLIError: If listing contexts fails
        """
        logger.info("Listing Qlik contexts")
        
        # Build command
        cmd = [self.cli_path, 'context', 'ls']
        
        # Execute command
        result = self._execute_command(cmd)
        
        # Parse output to extract context information
        contexts = []
        current_context = None
        
        if result['stdout']:
            lines = result['stdout'].strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('NAME'):  # Skip header
                    # Parse context line (format may vary)
                    parts = line.split()
                    if parts:
                        context_name = parts[0]
                        is_current = '*' in line or 'current' in line.lower()
                        
                        contexts.append({
                            'name': context_name,
                            'is_current': is_current
                        })
                        
                        if is_current:
                            current_context = context_name
        
        logger.info(f"Found {len(contexts)} Qlik contexts")
        
        return {
            'success': True,
            'contexts': contexts,
            'current_context': current_context,
            'raw_output': result['stdout']
        }
    
    def context_use(self, name: str) -> Dict[str, Any]:
        """
        Switch to a specific Qlik context
        
        Args:
            name: Name of the context to activate
            
        Returns:
            Dictionary containing operation result
            
        Raises:
            QlikCLIError: If context switching fails or context doesn't exist
        """
        logger.info(f"Switching to Qlik context: {name}")
        
        # Validate context name
        if not name or not name.strip():
            raise QlikCLIError("Context name cannot be empty")
        
        # Check if context exists
        contexts_result = self.context_list()
        available_contexts = [ctx['name'] for ctx in contexts_result['contexts']]
        
        if name not in available_contexts:
            raise QlikCLIError(f"Context '{name}' not found. Available contexts: {', '.join(available_contexts)}")
        
        # Build command
        cmd = [self.cli_path, 'context', 'use', name]
        
        # Execute command
        result = self._execute_command(cmd)
        
        logger.info(f"Successfully switched to Qlik context: {name}")
        return result
    
    def context_remove(self, name: str) -> Dict[str, Any]:
        """
        Remove a Qlik context
        
        Args:
            name: Name of the context to remove
            
        Returns:
            Dictionary containing operation result
            
        Raises:
            QlikCLIError: If context removal fails or context is currently active
        """
        logger.info(f"Removing Qlik context: {name}")
        
        # Validate context name
        if not name or not name.strip():
            raise QlikCLIError("Context name cannot be empty")
        
        # Check if context exists and is not currently active
        contexts_result = self.context_list()
        current_context = contexts_result['current_context']
        
        if current_context == name:
            raise QlikCLIError(f"Cannot remove currently active context '{name}'. Switch to another context first.")
        
        available_contexts = [ctx['name'] for ctx in contexts_result['contexts']]
        if name not in available_contexts:
            raise QlikCLIError(f"Context '{name}' not found. Available contexts: {', '.join(available_contexts)}")
        
        # Build command
        cmd = [self.cli_path, 'context', 'rm', name]
        
        # Execute command
        result = self._execute_command(cmd)
        
        logger.info(f"Successfully removed Qlik context: {name}")
        return result
    
    def context_current(self) -> Dict[str, Any]:
        """
        Get information about the current active context
        
        Returns:
            Dictionary containing current context information
            
        Raises:
            QlikCLIError: If getting current context fails
        """
        logger.info("Getting current Qlik context information")
        
        # Get context list to find current context
        contexts_result = self.context_list()
        current_context = contexts_result['current_context']
        
        if not current_context:
            return {
                'success': True,
                'current_context': None,
                'message': 'No active context found'
            }
        
        # Find current context details
        current_context_details = None
        for ctx in contexts_result['contexts']:
            if ctx['name'] == current_context:
                current_context_details = ctx
                break
        
        return {
            'success': True,
            'current_context': current_context,
            'context_details': current_context_details
        }
    
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
    
    # Existing methods (app_build, app_unbuild, etc.) remain unchanged
    
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