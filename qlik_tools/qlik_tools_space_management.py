"""
Qlik Space Management Tools

This module provides methods for space management operations.
"""

import logging
from typing import Dict, List, Optional, Any

from .qlik_cli_base import QlikCLI, QlikCLIError

# Configure logging
logger = logging.getLogger(__name__)


class QlikSpaceManagementMixin:
    """Mixin class for space management operations"""
    
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