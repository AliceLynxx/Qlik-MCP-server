"""
Qlik App Discovery Tools

This module provides methods for app discovery including
list, get, and search operations.
"""

import logging
from typing import Dict, List, Optional, Any

from .qlik_cli_base import QlikCLI, QlikCLIError

# Configure logging
logger = logging.getLogger(__name__)


class QlikAppDiscoveryMixin:
    """Mixin class for app discovery operations"""
    
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