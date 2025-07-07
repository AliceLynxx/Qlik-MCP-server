"""
Configuration module for Qlik-MCP-server

This module provides configuration settings and environment management
for the MCP server that interfaces with Qlik Cloud via qlik-cli.
Supports both direct authentication and context-based multi-tenant authentication.
"""

import os
from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class QlikConfig(BaseModel):
    """Configuration for Qlik CLI integration"""
    
    # Qlik CLI executable path
    cli_path: str = Field(
        default="qlik",
        description="Path to qlik-cli executable"
    )
    
    # Qlik Cloud connection settings (legacy/direct mode)
    tenant_url: Optional[str] = Field(
        default=None,
        description="Qlik Cloud tenant URL (used when not using contexts)"
    )
    
    # Authentication settings (legacy/direct mode)
    api_key: Optional[str] = Field(
        default=None,
        description="Qlik Cloud API key for authentication (used when not using contexts)"
    )
    
    # Context management settings
    context_support: bool = Field(
        default=True,
        description="Enable context-based authentication for multi-tenant support"
    )
    
    context_directory: Optional[str] = Field(
        default=None,
        description="Directory for storing context configurations (defaults to qlik-cli default)"
    )
    
    # App unbuild settings
    default_unbuild_directory: Optional[str] = Field(
        default=None,
        description="Default directory for app unbuild operations"
    )
    
    include_file_contents_in_output: bool = Field(
        default=True,
        description="Include file contents in unbuild output"
    )
    
    # Timeout settings
    command_timeout: int = Field(
        default=300,
        description="Timeout for qlik-cli commands in seconds"
    )
    
    def validate_context_directory(self) -> bool:
        """
        Validate that context directory exists and is accessible
        
        Returns:
            True if directory is valid or None (using default), False otherwise
        """
        if not self.context_directory:
            # Using qlik-cli default directory, assume it's valid
            return True
        
        try:
            context_path = Path(self.context_directory)
            if context_path.exists():
                return context_path.is_dir() and os.access(context_path, os.R_OK | os.W_OK)
            else:
                # Check if parent directory exists and is writable
                parent = context_path.parent
                return parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)
        except (OSError, ValueError):
            return False

    def validate_unbuild_directory(self) -> bool:
        """
        Validate that unbuild directory exists and is accessible
        
        Returns:
            True if directory is valid or None (no default), False otherwise
        """
        if not self.default_unbuild_directory:
            # No default directory configured, this is valid
            return True
        
        try:
            unbuild_path = Path(self.default_unbuild_directory)
            if unbuild_path.exists():
                return unbuild_path.is_dir() and os.access(unbuild_path, os.R_OK | os.W_OK)
            else:
                # Check if parent directory exists and is writable
                parent = unbuild_path.parent
                return parent.exists() and parent.is_dir() and os.access(parent, os.W_OK)
        except (OSError, ValueError):
            return False

    def get_unbuild_directory(self) -> Optional[str]:
        """
        Get the default unbuild directory, creating it if necessary
        
        Returns:
            Path to unbuild directory or None if not configured
        """
        if not self.default_unbuild_directory:
            return None
        
        try:
            unbuild_path = Path(self.default_unbuild_directory)
            if not unbuild_path.exists():
                unbuild_path.mkdir(parents=True, exist_ok=True)
            return str(unbuild_path)
        except (OSError, ValueError):
            return None


class ServerConfig(BaseModel):
    """Configuration for MCP server"""
    
    # Server identification
    name: str = Field(
        default="qlik-mcp-server",
        description="Server name for MCP identification"
    )
    
    version: str = Field(
        default="1.0.0",
        description="Server version"
    )
    
    # Logging configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # Development settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )


class Config(BaseModel):
    """Main configuration class combining all settings"""
    
    qlik: QlikConfig = Field(default_factory=QlikConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables"""
        
        qlik_config = QlikConfig(
            cli_path=os.getenv('QLIK_CLI_PATH', 'qlik'),
            tenant_url=os.getenv('QLIK_TENANT_URL'),
            api_key=os.getenv('QLIK_API_KEY'),
            context_support=os.getenv('QLIK_CONTEXT_SUPPORT', 'true').lower() == 'true',
            context_directory=os.getenv('QLIK_CONTEXT_DIRECTORY'),
            default_unbuild_directory=os.getenv('QLIK_DEFAULT_UNBUILD_DIRECTORY'),
            include_file_contents_in_output=os.getenv('QLIK_INCLUDE_FILE_CONTENTS', 'true').lower() == 'true',
            command_timeout=int(os.getenv('QLIK_COMMAND_TIMEOUT', '300'))
        )
        
        server_config = ServerConfig(
            name=os.getenv('MCP_SERVER_NAME', 'qlik-mcp-server'),
            version=os.getenv('MCP_SERVER_VERSION', '1.0.0'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true'
        )
        
        return cls(qlik=qlik_config, server=server_config)
    
    def validate_qlik_setup(self) -> bool:
        """Validate that Qlik CLI is properly configured"""
        import subprocess
        
        try:
            # Test if qlik-cli is accessible
            result = subprocess.run(
                [self.qlik.cli_path, 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return False
            
            # If context support is enabled, validate context directory
            if self.qlik.context_support:
                if not self.qlik.validate_context_directory():
                    return False
            
            # Validate unbuild directory if configured
            if not self.qlik.validate_unbuild_directory():
                return False
            
            return True
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_authentication_mode(self) -> str:
        """
        Determine the authentication mode based on configuration
        
        Returns:
            'context' if using context-based authentication,
            'direct' if using direct API key authentication,
            'none' if no authentication is configured
        """
        if self.qlik.context_support:
            return 'context'
        elif self.qlik.tenant_url and self.qlik.api_key:
            return 'direct'
        else:
            return 'none'
    
    def is_context_mode(self) -> bool:
        """Check if context-based authentication is enabled"""
        return self.qlik.context_support
    
    def is_direct_mode(self) -> bool:
        """Check if direct authentication is configured"""
        return not self.qlik.context_support and bool(self.qlik.tenant_url and self.qlik.api_key)


# Global configuration instance
config = Config.from_env()