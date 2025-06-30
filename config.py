"""
Configuration module for Qlik-MCP-server

This module provides configuration settings and environment management
for the MCP server that interfaces with Qlik Cloud via qlik-cli.
"""

import os
from typing import Optional
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
    
    # Qlik Cloud connection settings
    tenant_url: Optional[str] = Field(
        default=None,
        description="Qlik Cloud tenant URL"
    )
    
    # Authentication settings
    api_key: Optional[str] = Field(
        default=None,
        description="Qlik Cloud API key for authentication"
    )
    
    # Timeout settings
    command_timeout: int = Field(
        default=300,
        description="Timeout for qlik-cli commands in seconds"
    )


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
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


# Global configuration instance
config = Config.from_env()