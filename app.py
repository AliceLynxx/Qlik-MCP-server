#!/usr/bin/env python3
"""
Qlik MCP Server

FastMCP server implementation that provides Qlik Cloud functionality
through MCP (Model Context Protocol) tools. This server allows MCP clients
to build and unbuild Qlik applications using the qlik-cli.
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
    logger.info("  - qlik_app_build: Build Qlik applications from components")
    logger.info("  - qlik_app_unbuild: Export Qlik applications to components")
    logger.info("  - qlik_cli_version: Get qlik-cli version information")
    logger.info("  - qlik_validate_connection: Validate connection to Qlik Cloud")
    
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