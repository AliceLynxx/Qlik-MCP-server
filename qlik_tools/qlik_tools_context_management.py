"""
Qlik Context Management Tools

This module provides methods for context management operations.
"""

import logging
from typing import Dict, List, Optional, Any

from .qlik_cli_base import QlikCLI, QlikCLIError

# Configure logging
logger = logging.getLogger(__name__)


class QlikContextManagementMixin:
    """Mixin class for context management operations"""
    
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