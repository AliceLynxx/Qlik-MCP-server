#!/usr/bin/env python3
"""
Qlik MCP Server

FastMCP server implementation that provides Qlik Cloud functionality
through MCP (Model Context Protocol) tools. This server allows MCP clients
to build and unbuild Qlik applications using the qlik-cli, discover and list
applications, search through app catalogs, manage spaces, handle
authentication contexts for multi-tenant environments, and perform
app lifecycle operations like export, import, copy, and publish.
"""

import logging
import sys
from typing import Dict, Any, List, Optional, Union

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from config import Config
from qlik_tools import QlikCLI, QlikCLIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('qlik-mcp-server.log')
    ]
)

logger = logging.getLogger(__name__)

# Initialize configuration
config = Config.from_env()

# Set logging level from config
logging.getLogger().setLevel(getattr(logging, config.server.log_level.upper()))

# Initialize FastMCP server
mcp = FastMCP(config.server.name)

# Initialize QlikCLI
try:
    qlik_cli = QlikCLI(config)
    logger.info("QlikCLI initialized successfully")
except QlikCLIError as e:
    logger.error(f"Failed to initialize QlikCLI: {e}")
    sys.exit(1)


# Pydantic models for MCP tool parameters

class QlikAppBuildParams(BaseModel):
    """Parameters for qlik app build command"""
    app: str = Field(description="Name or identifier of the app")
    connections: Optional[str] = Field(None, description="Path to a yml file containing data connection definitions")
    script: Optional[str] = Field(None, description="Path to a qvs file containing the app data reload script")
    dimensions: Optional[Union[str, List[str]]] = Field(None, description="A list of generic dimension json paths")
    measures: Optional[Union[str, List[str]]] = Field(None, description="A list of generic measures json paths")
    objects: Optional[Union[str, List[str]]] = Field(None, description="A list of generic object json paths")
    variables: Optional[Union[str, List[str]]] = Field(None, description="A list of generic variable json paths")
    bookmarks: Optional[Union[str, List[str]]] = Field(None, description="A list of generic bookmark json paths")
    app_properties: Optional[str] = Field(None, description="Path to a json file containing the app properties")
    limit: Optional[int] = Field(None, description="Limit the number of rows to load")
    no_data: bool = Field(False, description="Open app without data")
    no_reload: bool = Field(False, description="Do not run the reload script")
    no_save: bool = Field(False, description="Do not save the app")
    silent: bool = Field(False, description="Do not log reload output")


class QlikAppUnbuildParams(BaseModel):
    """Parameters for qlik app unbuild command"""
    app: str = Field(description="Name or identifier of the app")
    dir: Optional[str] = Field(None, description="Path to the folder where the unbuilt app is exported")
    no_data: bool = Field(False, description="Open app without data")


class QlikAppExportParams(BaseModel):
    """Parameters for exporting Qlik applications"""
    app_identifier: str = Field(description="App ID or name to export")
    output_path: str = Field(description="Path where exported file will be saved")
    format: str = Field(default="qvf", description="Export format: 'qvf', 'json', or 'xlsx'")
    include_data: bool = Field(default=True, description="Whether to include data in export")
    no_data: bool = Field(default=False, description="Export without data (only metadata/script)")


class QlikAppImportParams(BaseModel):
    """Parameters for importing Qlik applications"""
    file_path: str = Field(description="Path to import file (QVF format)")
    app_name: Optional[str] = Field(None, description="Name for new app (optional, will use file name if not provided)")
    space_id: Optional[str] = Field(None, description="Target space for import (optional, uses personal space if not provided)")
    replace_existing: bool = Field(default=False, description="Whether to replace existing app with same name")
    validate_before_import: bool = Field(default=True, description="Whether to validate file before import")


class QlikAppCopyParams(BaseModel):
    """Parameters for copying Qlik applications"""
    source_app_id: str = Field(description="Source app ID to copy from")
    target_name: str = Field(description="Name for the copied app")
    target_space_id: Optional[str] = Field(None, description="Target space ID (optional, uses source app space if not provided)")
    include_data: bool = Field(default=True, description="Whether to include data in the copy")
    copy_permissions: bool = Field(default=False, description="Whether to copy permissions")


class QlikAppPublishParams(BaseModel):
    """Parameters for publishing Qlik applications"""
    app_id: str = Field(description="App ID to publish")
    target_space_id: str = Field(description="Managed space ID to publish to")
    publish_name: Optional[str] = Field(None, description="Name for published app (optional, uses original name if not provided)")
    replace_existing: bool = Field(default=False, description="Whether to replace existing published app")


class QlikAppListParams(BaseModel):
    """Parameters for listing Qlik applications"""
    space_id: Optional[str] = Field(None, description="Filter by specific space ID")
    collection_id: Optional[str] = Field(None, description="Filter by specific collection ID")
    owner: Optional[str] = Field(None, description="Filter by app owner name")
    limit: int = Field(50, description="Maximum number of apps to return (default: 50)")
    offset: int = Field(0, description="Number of apps to skip for pagination (default: 0)")


class QlikAppGetParams(BaseModel):
    """Parameters for getting specific app details"""
    app_identifier: str = Field(description="App ID or name to retrieve details for")


class QlikAppSearchParams(BaseModel):
    """Parameters for searching Qlik applications"""
    query: str = Field(description="Search query string to match against app names, descriptions, and tags")
    limit: int = Field(20, description="Maximum number of search results to return (default: 20)")
    space_id: Optional[str] = Field(None, description="Filter results by specific space ID")
    owner: Optional[str] = Field(None, description="Filter results by app owner name")


class QlikSpaceListParams(BaseModel):
    """Parameters for listing Qlik spaces"""
    type_filter: Optional[str] = Field(None, description="Filter by space type: 'personal', 'shared', or 'managed'")


class QlikContextCreateParams(BaseModel):
    """Parameters for creating a new Qlik context"""
    name: str = Field(description="Name for the new context")
    tenant_url: str = Field(description="Qlik Cloud tenant URL (e.g., https://your-tenant.qlikcloud.com)")
    api_key: str = Field(description="API key for authentication with Qlik Cloud")


class QlikContextUseParams(BaseModel):
    """Parameters for switching to a Qlik context"""
    name: str = Field(description="Name of the context to activate")


class QlikContextRemoveParams(BaseModel):
    """Parameters for removing a Qlik context"""
    name: str = Field(description="Name of the context to remove")


# App Export and Import Tools

@mcp.tool()
def qlik_app_export(params: QlikAppExportParams) -> Dict[str, Any]:
    """
    Export Qlik application to local file for backup, migration, or version control
    
    This tool exports a Qlik application to various formats (QVF, JSON, XLSX) for
    backup, migration between environments, or version control purposes. It supports
    exporting with or without data and provides progress feedback for large exports.
    The exported files can be used for app lifecycle management, DevOps workflows,
    and collaboration between teams.
    
    Args:
        params: QlikAppExportParams containing export configuration
        
    Returns:
        Dictionary containing export result, file information, and operation details
        
    Raises:
        Exception: If the export operation fails
    """
    logger.info(f"Exporting Qlik app '{params.app_identifier}' to '{params.output_path}'")
    
    try:
        # Execute the app export
        result = qlik_cli.app_export(
            app_identifier=params.app_identifier,
            output_path=params.output_path,
            format=params.format,
            include_data=params.include_data,
            no_data=params.no_data
        )
        
        # Format the output for better readability
        export_summary = {
            'app_identifier': result['app_identifier'],
            'output_file': result['output_path'],
            'format': result['format'].upper(),
            'file_size': f"{result['file_size_mb']} MB ({result['file_size_bytes']:,} bytes)",
            'includes_data': result['include_data'],
            'export_duration': f"{result['export_duration_seconds']} seconds"
        }
        
        logger.info(f"Successfully exported app '{params.app_identifier}' ({result['file_size_mb']} MB)")
        
        return {
            "success": True,
            "message": f"Successfully exported '{params.app_identifier}' to {params.format.upper()} format",
            "export_summary": export_summary,
            "file_path": result['output_path'],
            "recommendations": [
                "Verify the exported file can be opened in Qlik Sense",
                "Store the file in a secure location for backup purposes",
                "Consider version control integration for collaborative development"
            ]
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to export Qlik app '{params.app_identifier}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error exporting Qlik app '{params.app_identifier}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_import(params: QlikAppImportParams) -> Dict[str, Any]:
    """
    Import Qlik application from local file to create new app in tenant
    
    This tool imports a Qlik application from a local QVF file, creating a new app
    in the specified space. It includes pre-import validation, conflict detection,
    and post-import verification. This is essential for app migration, deployment
    workflows, and restoring apps from backups.
    
    Args:
        params: QlikAppImportParams containing import configuration
        
    Returns:
        Dictionary containing import result, new app information, and verification details
        
    Raises:
        Exception: If the import operation fails
    """
    logger.info(f"Importing Qlik app from '{params.file_path}' with name '{params.app_name}'")
    
    try:
        # Execute the app import
        result = qlik_cli.app_import(
            file_path=params.file_path,
            app_name=params.app_name,
            space_id=params.space_id,
            replace_existing=params.replace_existing,
            validate_before_import=params.validate_before_import
        )
        
        # Format the output for better readability
        import_summary = {
            'source_file': result['file_path'],
            'app_name': result['app_name'],
            'new_app_id': result['new_app_id'] or 'Not available',
            'target_space': result['space_id'] or 'Personal Space',
            'replaced_existing': 'Yes' if result['replaced_existing'] else 'No',
            'import_duration': f"{result['import_duration_seconds']} seconds",
            'verification_status': 'Verified' if result['verification_result'] else 'Could not verify'
        }
        
        # Add verification details if available
        verification_info = []
        if result['verification_result'] and result['verification_result']['success']:
            app_details = result['verification_result']['app']
            verification_info = [
                f"App successfully created with ID: {result['new_app_id']}",
                f"App is located in space: {app_details['space']['name']}",
                f"App owner: {app_details['owner']['name']}",
                f"App has data: {'Yes' if app_details['has_data'] else 'No'}"
            ]
        
        logger.info(f"Successfully imported app '{result['app_name']}' (ID: {result['new_app_id']})")
        
        return {
            "success": True,
            "message": f"Successfully imported '{result['app_name']}' from {params.file_path}",
            "import_summary": import_summary,
            "new_app_id": result['new_app_id'],
            "verification_details": verification_info,
            "next_steps": [
                "Open the app in Qlik Sense to verify functionality",
                "Check data connections if the app uses external data sources",
                "Review and update app permissions as needed",
                "Consider publishing to a managed space for broader access"
            ]
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to import Qlik app from '{params.file_path}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error importing Qlik app from '{params.file_path}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_copy(params: QlikAppCopyParams) -> Dict[str, Any]:
    """
    Copy existing Qlik application within the same tenant
    
    This tool creates a copy of an existing Qlik application within the same tenant,
    optionally copying to a different space. It supports copying with or without data
    and can preserve permissions. This is useful for creating development copies,
    templates, or distributing apps across different spaces.
    
    Args:
        params: QlikAppCopyParams containing copy configuration
        
    Returns:
        Dictionary containing copy result, new app information, and operation details
        
    Raises:
        Exception: If the copy operation fails
    """
    logger.info(f"Copying Qlik app '{params.source_app_id}' to new app '{params.target_name}'")
    
    try:
        # Execute the app copy
        result = qlik_cli.app_copy(
            source_app_id=params.source_app_id,
            target_name=params.target_name,
            target_space_id=params.target_space_id,
            include_data=params.include_data,
            copy_permissions=params.copy_permissions
        )
        
        # Format the output for better readability
        copy_summary = {
            'source_app': {
                'id': result['source_app_id'],
                'name': result['source_app_name']
            },
            'target_app': {
                'id': result['new_app_id'] or 'Not available',
                'name': result['target_name']
            },
            'target_space_id': result['target_space_id'],
            'data_included': 'Yes' if result['include_data'] else 'No',
            'permissions_copied': 'Yes' if result['copy_permissions'] else 'No',
            'copy_duration': f"{result['copy_duration_seconds']} seconds",
            'verification_status': 'Verified' if result['verification_result'] else 'Could not verify'
        }
        
        # Add verification details if available
        verification_info = []
        if result['verification_result'] and result['verification_result']['success']:
            app_details = result['verification_result']['app']
            verification_info = [
                f"Copy successfully created with ID: {result['new_app_id']}",
                f"Copy is located in space: {app_details['space']['name']}",
                f"Copy owner: {app_details['owner']['name']}",
                f"Copy has data: {'Yes' if app_details['has_data'] else 'No'}"
            ]
        
        logger.info(f"Successfully copied app '{params.source_app_id}' to '{result['target_name']}' (ID: {result['new_app_id']})")
        
        return {
            "success": True,
            "message": f"Successfully copied '{result['source_app_name']}' to '{result['target_name']}'",
            "copy_summary": copy_summary,
            "new_app_id": result['new_app_id'],
            "verification_details": verification_info,
            "recommendations": [
                "Open the copied app to verify all functionality works correctly",
                "Update any hardcoded references that might point to the original app",
                "Review and adjust permissions for the copied app as needed",
                "Consider renaming objects within the app to reflect the new purpose"
            ]
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to copy Qlik app '{params.source_app_id}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error copying Qlik app '{params.source_app_id}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_publish(params: QlikAppPublishParams) -> Dict[str, Any]:
    """
    Publish Qlik application to managed space for broader access
    
    This tool publishes a Qlik application from a personal or shared space to a
    managed space, making it available to a broader audience. It validates managed
    space permissions, handles naming conflicts, and provides publication status
    tracking. This is essential for promoting apps from development to production.
    
    Args:
        params: QlikAppPublishParams containing publication configuration
        
    Returns:
        Dictionary containing publication result, published app information, and details
        
    Raises:
        Exception: If the publication operation fails
    """
    logger.info(f"Publishing Qlik app '{params.app_id}' to managed space '{params.target_space_id}'")
    
    try:
        # Execute the app publication
        result = qlik_cli.app_publish(
            app_id=params.app_id,
            target_space_id=params.target_space_id,
            publish_name=params.publish_name,
            replace_existing=params.replace_existing
        )
        
        # Format the output for better readability
        publish_summary = {
            'source_app': {
                'id': result['source_app_id'],
                'name': result['source_app_name']
            },
            'published_app': {
                'id': result['published_app_id'] or 'Not available',
                'name': result['publish_name']
            },
            'target_space': {
                'id': result['target_space_id'],
                'name': result['target_space_name']
            },
            'replaced_existing': 'Yes' if result['replaced_existing'] else 'No',
            'publish_duration': f"{result['publish_duration_seconds']} seconds",
            'verification_status': 'Verified' if result['verification_result'] else 'Could not verify'
        }
        
        # Add verification details if available
        verification_info = []
        if result['verification_result'] and result['verification_result']['success']:
            app_details = result['verification_result']['app']
            verification_info = [
                f"App successfully published with ID: {result['published_app_id']}",
                f"Published app is in managed space: {result['target_space_name']}",
                f"Published app owner: {app_details['owner']['name']}",
                f"App is now accessible to space members"
            ]
        
        logger.info(f"Successfully published app '{params.app_id}' to space '{result['target_space_name']}' (Published ID: {result['published_app_id']})")
        
        return {
            "success": True,
            "message": f"Successfully published '{result['source_app_name']}' to managed space '{result['target_space_name']}'",
            "publish_summary": publish_summary,
            "published_app_id": result['published_app_id'],
            "verification_details": verification_info,
            "next_steps": [
                "Verify the published app is accessible to intended users",
                "Update any bookmarks or links to point to the published version",
                "Consider setting up automated refresh schedules if needed",
                "Review and configure appropriate access permissions for space members"
            ]
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to publish Qlik app '{params.app_id}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error publishing Qlik app '{params.app_id}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


# App Discovery Tools

@mcp.tool()
def qlik_app_list(params: QlikAppListParams) -> Dict[str, Any]:
    """
    List available Qlik applications with filtering options
    
    This tool retrieves a list of Qlik applications from your tenant with support
    for filtering by space, owner, and pagination. It provides essential information
    about each app including name, owner, space, creation/modification dates, and tags.
    This is the primary tool for discovering what apps are available in your environment.
    
    Args:
        params: QlikAppListParams containing filtering and pagination options
        
    Returns:
        Dictionary containing the list of apps and metadata
        
    Raises:
        Exception: If the app listing operation fails
    """
    logger.info(f"Listing Qlik apps with filters: space_id={params.space_id}, owner={params.owner}")
    
    try:
        # Execute the app listing
        result = qlik_cli.app_list(
            space_id=params.space_id,
            collection_id=params.collection_id,
            owner=params.owner,
            limit=params.limit,
            offset=params.offset
        )
        
        # Format the output for better readability
        apps = result['apps']
        
        # Create summary information
        summary = {
            'total_apps': len(apps),
            'filters_applied': result['filters_applied'],
            'spaces_represented': len(set(app['space_name'] for app in apps if app['space_name'])),
            'owners_represented': len(set(app['owner'] for app in apps if app['owner']))
        }
        
        # Format apps for display
        formatted_apps = []
        for app in apps:
            formatted_app = {
                'name': app['name'],
                'id': app['id'],
                'owner': app['owner'],
                'space': app['space_name'] or 'Personal',
                'modified': app['modified_date'][:10] if app['modified_date'] else 'Unknown',  # Just date part
                'published': 'Yes' if app['published'] else 'No',
                'tags': ', '.join(app['tags']) if app['tags'] else 'None',
                'description': app['description'][:100] + '...' if len(app.get('description', '')) > 100 else app.get('description', '')
            }
            formatted_apps.append(formatted_app)
        
        logger.info(f"Successfully listed {len(apps)} Qlik apps")
        
        return {
            "success": True,
            "message": f"Found {len(apps)} Qlik applications",
            "summary": summary,
            "apps": formatted_apps,
            "pagination": {
                "limit": params.limit,
                "offset": params.offset,
                "returned": len(apps)
            }
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to list Qlik apps: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error listing Qlik apps: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_get(params: QlikAppGetParams) -> Dict[str, Any]:
    """
    Get detailed information about a specific Qlik application
    
    This tool retrieves comprehensive details about a specific Qlik application,
    including metadata, ownership, space information, reload status, file size,
    and other technical details. Use this when you need complete information
    about a particular app for analysis or management purposes.
    
    Args:
        params: QlikAppGetParams containing the app identifier
        
    Returns:
        Dictionary containing detailed app information
        
    Raises:
        Exception: If the app retrieval operation fails or app doesn't exist
    """
    logger.info(f"Getting details for Qlik app: {params.app_identifier}")
    
    try:
        # Execute the app details retrieval
        result = qlik_cli.app_get(params.app_identifier)
        
        app = result['app']
        
        # Format the output for better readability
        formatted_app = {
            'basic_info': {
                'name': app['name'],
                'id': app['id'],
                'description': app['description'] or 'No description',
                'usage': app['usage']
            },
            'ownership': {
                'owner_name': app['owner']['name'],
                'owner_id': app['owner']['id'],
                'owner_email': app['owner']['email'] or 'Not available'
            },
            'space_info': {
                'space_name': app['space']['name'] or 'Personal Space',
                'space_id': app['space']['id'],
                'space_type': app['space']['type'] or 'personal'
            },
            'dates': {
                'created': app['created_date'][:19] if app['created_date'] else 'Unknown',  # Remove timezone
                'modified': app['modified_date'][:19] if app['modified_date'] else 'Unknown',
                'last_reload': app['last_reload_time'][:19] if app['last_reload_time'] else 'Never'
            },
            'status': {
                'published': 'Yes' if app['published'] else 'No',
                'has_data': 'Yes' if app['has_data'] else 'No',
                'direct_query_mode': 'Yes' if app['is_direct_query_mode'] else 'No'
            },
            'technical_details': {
                'file_size_bytes': app['file_size'],
                'file_size_mb': round(app['file_size'] / (1024 * 1024), 2) if app['file_size'] else 0,
                'tags': app['tags'] if app['tags'] else [],
                'custom_properties_count': len(app['custom_properties']),
                'attributes_count': len(app['attributes'])
            }
        }
        
        # Add origin/target app info if available
        if app['origin_app_id']:
            formatted_app['relationships'] = {
                'origin_app_id': app['origin_app_id'],
                'target_app_id': app['target_app_id'] or 'None'
            }
        
        logger.info(f"Successfully retrieved details for app: {params.app_identifier}")
        
        return {
            "success": True,
            "message": f"Retrieved details for app: {app['name']}",
            "app_details": formatted_app
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to get Qlik app details for '{params.app_identifier}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error getting Qlik app details for '{params.app_identifier}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_search(params: QlikAppSearchParams) -> Dict[str, Any]:
    """
    Search for Qlik applications by name, description, or tags
    
    This tool performs a comprehensive search across your Qlik applications,
    matching the query against app names, descriptions, and tags. Results are
    ranked by relevance and can be filtered by space or owner. Use this when
    you need to find specific apps but don't know their exact names.
    
    Args:
        params: QlikAppSearchParams containing search query and filters
        
    Returns:
        Dictionary containing search results with relevance scoring
        
    Raises:
        Exception: If the search operation fails
    """
    logger.info(f"Searching Qlik apps with query: '{params.query}'")
    
    try:
        # Build filters dictionary
        filters = {}
        if params.space_id:
            filters['space_id'] = params.space_id
        if params.owner:
            filters['owner'] = params.owner
        
        # Execute the search
        result = qlik_cli.app_search(
            query=params.query,
            limit=params.limit,
            filters=filters if filters else None
        )
        
        apps = result['apps']
        
        # Format the output for better readability
        formatted_apps = []
        for app in apps:
            formatted_app = {
                'name': app['name'],
                'id': app['id'],
                'owner': app['owner'],
                'space': app['space_name'] or 'Personal',
                'relevance_score': app['relevance_score'],
                'match_reasons': ', '.join(app['match_reasons']),
                'description': app['description'][:150] + '...' if len(app.get('description', '')) > 150 else app.get('description', ''),
                'tags': ', '.join(app['tags']) if app['tags'] else 'None',
                'modified': app['modified_date'][:10] if app['modified_date'] else 'Unknown'
            }
            formatted_apps.append(formatted_app)
        
        # Create search summary
        search_summary = {
            'query': params.query,
            'total_matches': len(apps),
            'searched_through': result['search_performed_on'],
            'filters_applied': result['filters_applied'],
            'top_match': apps[0]['name'] if apps else 'No matches found'
        }
        
        logger.info(f"Found {len(apps)} matching apps for query: '{params.query}'")
        
        return {
            "success": True,
            "message": f"Found {len(apps)} apps matching '{params.query}'",
            "search_summary": search_summary,
            "results": formatted_apps
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to search Qlik apps with query '{params.query}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error searching Qlik apps with query '{params.query}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_space_list(params: QlikSpaceListParams) -> Dict[str, Any]:
    """
    List available Qlik spaces with type filtering
    
    This tool retrieves information about all Qlik spaces you have access to,
    including personal, shared, and managed spaces. It shows space details,
    ownership, and the number of apps in each space. Use this to understand
    your space structure and find where apps are organized.
    
    Args:
        params: QlikSpaceListParams containing optional type filter
        
    Returns:
        Dictionary containing list of spaces with details and app counts
        
    Raises:
        Exception: If the space listing operation fails
    """
    logger.info(f"Listing Qlik spaces with type filter: {params.type_filter}")
    
    try:
        # Execute the space listing
        result = qlik_cli.space_list(type_filter=params.type_filter)
        
        spaces = result['spaces']
        
        # Format the output for better readability
        formatted_spaces = []
        for space in spaces:
            formatted_space = {
                'name': space['name'],
                'id': space['id'],
                'type': space['type'].title(),
                'owner': space['owner']['name'] if space['owner']['name'] else 'System',
                'description': space['description'][:100] + '...' if len(space.get('description', '')) > 100 else space.get('description', 'No description'),
                'app_count': space['app_count'] if space['app_count'] >= 0 else 'Unknown',
                'created': space['created_date'][:10] if space['created_date'] else 'Unknown',
                'modified': space['modified_date'][:10] if space['modified_date'] else 'Unknown'
            }
            formatted_spaces.append(formatted_space)
        
        # Create summary information
        space_summary = {
            'total_spaces': len(spaces),
            'type_filter': params.type_filter or 'All types',
            'space_types': {
                'personal': len([s for s in spaces if s['type'] == 'personal']),
                'shared': len([s for s in spaces if s['type'] == 'shared']),
                'managed': len([s for s in spaces if s['type'] == 'managed'])
            },
            'total_apps_across_spaces': sum(s['app_count'] for s in spaces if s['app_count'] >= 0)
        }
        
        logger.info(f"Successfully listed {len(spaces)} Qlik spaces")
        
        return {
            "success": True,
            "message": f"Found {len(spaces)} Qlik spaces",
            "summary": space_summary,
            "spaces": formatted_spaces
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to list Qlik spaces: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error listing Qlik spaces: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


# App Build/Unbuild Tools

@mcp.tool()
def qlik_app_build(params: QlikAppBuildParams) -> Dict[str, Any]:
    """
    Build a Qlik application using qlik-cli
    
    This tool creates or updates a Qlik application by building it from various
    components like scripts, dimensions, measures, objects, variables, and bookmarks.
    It provides comprehensive control over the build process including data loading,
    reload behavior, and save operations.
    
    Args:
        params: QlikAppBuildParams containing all build parameters
        
    Returns:
        Dictionary containing the build result and execution details
        
    Raises:
        Exception: If the build operation fails
    """
    logger.info(f"Starting qlik app build for app: {params.app}")
    
    try:
        # Convert Pydantic model to dict for QlikCLI
        build_params = params.model_dump(exclude_none=True)
        
        # Execute the build command
        result = qlik_cli.app_build(**build_params)
        
        logger.info(f"Successfully built Qlik app: {params.app}")
        
        return {
            "success": True,
            "message": f"Successfully built Qlik app: {params.app}",
            "app": params.app,
            "command_result": result,
            "parameters_used": build_params
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to build Qlik app '{params.app}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error building Qlik app '{params.app}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_app_unbuild(params: QlikAppUnbuildParams) -> Dict[str, Any]:
    """
    Unbuild a Qlik application using qlik-cli
    
    This tool exports a Qlik application by unbuilding it into its component parts
    such as scripts, dimensions, measures, objects, variables, and bookmarks.
    The components are saved to a specified directory for version control,
    backup, or migration purposes.
    
    Args:
        params: QlikAppUnbuildParams containing all unbuild parameters
        
    Returns:
        Dictionary containing the unbuild result and execution details
        
    Raises:
        Exception: If the unbuild operation fails
    """
    logger.info(f"Starting qlik app unbuild for app: {params.app}")
    
    try:
        # Convert Pydantic model to dict for QlikCLI
        unbuild_params = params.model_dump(exclude_none=True)
        
        # Execute the unbuild command
        result = qlik_cli.app_unbuild(**unbuild_params)
        
        logger.info(f"Successfully unbuilt Qlik app: {params.app}")
        
        return {
            "success": True,
            "message": f"Successfully unbuilt Qlik app: {params.app}",
            "app": params.app,
            "export_directory": params.dir or "current directory",
            "command_result": result,
            "parameters_used": unbuild_params
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to unbuild Qlik app '{params.app}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error unbuilding Qlik app '{params.app}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


# Context Management Tools

@mcp.tool()
def qlik_context_create(params: QlikContextCreateParams) -> Dict[str, Any]:
    """
    Create a new Qlik context for authentication
    
    This tool creates a new authentication context for Qlik Cloud, allowing users
    to securely store and manage API keys for different tenants or environments.
    The API key is validated against the tenant before the context is created.
    
    Args:
        params: QlikContextCreateParams containing context name, tenant URL, and API key
        
    Returns:
        Dictionary containing the context creation result
        
    Raises:
        Exception: If context creation fails or API key validation fails
    """
    logger.info(f"Creating Qlik context: {params.name}")
    
    try:
        # Execute the context creation
        result = qlik_cli.context_create(params.name, params.tenant_url, params.api_key)
        
        logger.info(f"Successfully created Qlik context: {params.name}")
        
        return {
            "success": True,
            "message": f"Successfully created Qlik context '{params.name}' for tenant {params.tenant_url}",
            "context_name": params.name,
            "tenant_url": params.tenant_url,
            "command_result": result
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to create Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error creating Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_context_list() -> Dict[str, Any]:
    """
    List all available Qlik contexts
    
    This tool retrieves and displays all configured Qlik contexts, showing
    which context is currently active. This helps users understand their
    available authentication configurations and switch between them as needed.
    
    Returns:
        Dictionary containing the list of contexts and current active context
        
    Raises:
        Exception: If listing contexts fails
    """
    logger.info("Listing Qlik contexts")
    
    try:
        # Execute the context listing
        result = qlik_cli.context_list()
        
        logger.info(f"Successfully listed Qlik contexts: {len(result['contexts'])} found")
        
        return {
            "success": True,
            "message": f"Found {len(result['contexts'])} Qlik contexts",
            "contexts": result['contexts'],
            "current_context": result['current_context'],
            "command_result": result
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to list Qlik contexts: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error listing Qlik contexts: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_context_use(params: QlikContextUseParams) -> Dict[str, Any]:
    """
    Switch to a specific Qlik context
    
    This tool activates a specific authentication context, making it the default
    for all subsequent Qlik operations. This allows users to easily switch between
    different tenants or environments without reconfiguring authentication.
    
    Args:
        params: QlikContextUseParams containing the context name to activate
        
    Returns:
        Dictionary containing the context switching result
        
    Raises:
        Exception: If context switching fails or context doesn't exist
    """
    logger.info(f"Switching to Qlik context: {params.name}")
    
    try:
        # Execute the context switch
        result = qlik_cli.context_use(params.name)
        
        logger.info(f"Successfully switched to Qlik context: {params.name}")
        
        return {
            "success": True,
            "message": f"Successfully switched to Qlik context '{params.name}'",
            "active_context": params.name,
            "command_result": result
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to switch to Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error switching to Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_context_remove(params: QlikContextRemoveParams) -> Dict[str, Any]:
    """
    Remove a Qlik context
    
    This tool permanently removes an authentication context and its associated
    credentials. The currently active context cannot be removed - users must
    switch to another context first. This provides a secure way to clean up
    unused or outdated authentication configurations.
    
    Args:
        params: QlikContextRemoveParams containing the context name to remove
        
    Returns:
        Dictionary containing the context removal result
        
    Raises:
        Exception: If context removal fails or context is currently active
    """
    logger.info(f"Removing Qlik context: {params.name}")
    
    try:
        # Execute the context removal
        result = qlik_cli.context_remove(params.name)
        
        logger.info(f"Successfully removed Qlik context: {params.name}")
        
        return {
            "success": True,
            "message": f"Successfully removed Qlik context '{params.name}'",
            "removed_context": params.name,
            "command_result": result
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to remove Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error removing Qlik context '{params.name}': {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


# Utility Tools

@mcp.tool()
def qlik_cli_version() -> Dict[str, Any]:
    """
    Get qlik-cli version information
    
    This tool retrieves version information from the qlik-cli executable
    to help with debugging and compatibility checking.
    
    Returns:
        Dictionary containing version information
    """
    logger.info("Getting qlik-cli version information")
    
    try:
        result = qlik_cli.get_cli_version()
        
        return {
            "success": True,
            "message": "Successfully retrieved qlik-cli version",
            "version_info": result
        }
        
    except QlikCLIError as e:
        error_msg = f"Failed to get qlik-cli version: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


@mcp.tool()
def qlik_validate_connection() -> Dict[str, Any]:
    """
    Validate connection to Qlik Cloud
    
    This tool tests the connection to Qlik Cloud to ensure that
    authentication and network connectivity are working properly.
    
    Returns:
        Dictionary containing connection validation result
    """
    logger.info("Validating connection to Qlik Cloud")
    
    try:
        is_valid = qlik_cli.validate_connection()
        
        if is_valid:
            return {
                "success": True,
                "message": "Connection to Qlik Cloud is valid",
                "connected": True
            }
        else:
            return {
                "success": False,
                "message": "Connection to Qlik Cloud failed",
                "connected": False
            }
            
    except Exception as e:
        error_msg = f"Error validating connection: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def main():
    """
    Main function to start the FastMCP server
    
    This function initializes and starts the MCP server, making the Qlik tools
    available to MCP clients. The server will run until interrupted.
    """
    logger.info(f"Starting {config.server.name} v{config.server.version}")
    logger.info(f"Debug mode: {config.server.debug}")
    logger.info(f"Log level: {config.server.log_level}")
    
    # Validate Qlik CLI setup
    if not config.validate_qlik_setup():
        logger.error("Qlik CLI setup validation failed. Please check your qlik-cli installation and configuration.")
        sys.exit(1)
    
    logger.info("Qlik CLI setup validation passed")
    
    # Log available tools
    logger.info("Available MCP tools:")
    logger.info("  App Lifecycle Management:")
    logger.info("    - qlik_app_export: Export apps to local files for backup/migration")
    logger.info("    - qlik_app_import: Import apps from local files to create new apps")
    logger.info("    - qlik_app_copy: Copy existing apps within the same tenant")
    logger.info("    - qlik_app_publish: Publish apps to managed spaces")
    logger.info("  App Discovery:")
    logger.info("    - qlik_app_list: List available apps with filtering options")
    logger.info("    - qlik_app_get: Get detailed information about a specific app")
    logger.info("    - qlik_app_search: Search apps by name, description, or tags")
    logger.info("    - qlik_space_list: List available spaces with app counts")
    logger.info("  App Management:")
    logger.info("    - qlik_app_build: Build Qlik applications from components")
    logger.info("    - qlik_app_unbuild: Export Qlik applications to components")
    logger.info("  Context Management:")
    logger.info("    - qlik_context_create: Create new authentication context")
    logger.info("    - qlik_context_list: List all available contexts")
    logger.info("    - qlik_context_use: Switch to a specific context")
    logger.info("    - qlik_context_remove: Remove an authentication context")
    logger.info("  Utilities:")
    logger.info("    - qlik_cli_version: Get qlik-cli version information")
    logger.info("    - qlik_validate_connection: Validate connection to Qlik Cloud")
    
    try:
        # Start the MCP server
        logger.info("Starting MCP server...")
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
        
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)
        
    finally:
        logger.info("MCP server stopped")


if __name__ == "__main__":
    main()