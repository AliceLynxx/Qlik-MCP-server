"""
Qlik CLI Combined Module

This module combines all the separate tool modules into a single QlikCLI class
that provides all functionality in one interface.
"""

from .qlik_cli_base import QlikCLI as BaseQlikCLI, QlikCLIError
from .qlik_tools_app_lifecycle import QlikAppLifecycleMixin
from .qlik_tools_app_discovery import QlikAppDiscoveryMixin
from .qlik_tools_space_management import QlikSpaceManagementMixin
from .qlik_tools_app_build import QlikAppBuildMixin
from .qlik_tools_context_management import QlikContextManagementMixin


class QlikCLI(
    BaseQlikCLI,
    QlikAppLifecycleMixin,
    QlikAppDiscoveryMixin,
    QlikSpaceManagementMixin,
    QlikAppBuildMixin,
    QlikContextManagementMixin
):
    """
    Combined QlikCLI class that includes all functionality from separate modules.
    
    This class inherits from the base QlikCLI class and all mixin classes to provide
    a complete interface to all qlik-cli functionality organized by functional area:
    
    - App Lifecycle: export, import, copy, publish
    - App Discovery: list, get, search
    - Space Management: list spaces
    - App Build: build, unbuild
    - Context Management: create, list, use, remove contexts
    """
    
    def __init__(self, config):
        """
        Initialize the combined QlikCLI with all functionality.
        
        Args:
            config: Configuration object containing qlik-cli settings
        """
        super().__init__(config)


# Export the main classes for backward compatibility
__all__ = ['QlikCLI', 'QlikCLIError']