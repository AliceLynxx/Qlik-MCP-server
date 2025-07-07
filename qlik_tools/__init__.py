"""
Qlik Tools Package

This package provides a Python interface to qlik-cli commands,
organized into separate modules for different functionality areas.

The main QlikCLI class combines all functionality from the separate modules:
- App Lifecycle: export, import, copy, publish
- App Discovery: list, get, search  
- Space Management: list spaces
- App Build: build, unbuild
- Context Management: create, list, use, remove contexts

Usage:
    from qlik_tools import QlikCLI, QlikCLIError
    
    # Initialize with config
    qlik_cli = QlikCLI(config)
    
    # Use any of the available methods
    apps = qlik_cli.app_list()
    result = qlik_cli.app_export('my-app', '/path/to/export.qvf')
"""

from .qlik_cli_combined import QlikCLI, QlikCLIError

# Also export individual modules for advanced usage
from . import qlik_cli_base
from . import qlik_tools_app_lifecycle
from . import qlik_tools_app_discovery
from . import qlik_tools_space_management
from . import qlik_tools_app_build
from . import qlik_tools_context_management

__all__ = [
    'QlikCLI', 
    'QlikCLIError',
    'qlik_cli_base',
    'qlik_tools_app_lifecycle',
    'qlik_tools_app_discovery', 
    'qlik_tools_space_management',
    'qlik_tools_app_build',
    'qlik_tools_context_management'
]