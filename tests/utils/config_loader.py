"""
Configuration loader for test framework.
Loads and validates configuration files.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import os


class ConfigLoader:
    """Load and manage test configuration."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config loader.
        
        Args:
            config_dir: Path to config directory. Defaults to tests/config/
        """
        if config_dir is None:
            # Get the tests directory (parent of utils)
            tests_dir = Path(__file__).parent.parent
            config_dir = tests_dir / "config"
        
        self.config_dir = Path(config_dir)
        self._config: Optional[Dict[str, Any]] = None
        self._test_users: Optional[Dict[str, Any]] = None
        self._environments: Optional[Dict[str, Any]] = None
        self._current_environment: str = "local"
    
    def load_config(self) -> Dict[str, Any]:
        """Load main configuration file.
        
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if self._config is None:
            config_file = self.config_dir / "config.json"
            if not config_file.exists():
                raise FileNotFoundError(f"Config file not found: {config_file}")
            
            with open(config_file, 'r') as f:
                self._config = json.load(f)
        
        return self._config
    
    def load_test_users(self) -> Dict[str, Any]:
        """Load test users configuration.
        
        Returns:
            Test users dictionary
            
        Raises:
            FileNotFoundError: If test users file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        if self._test_users is None:
            users_file = self.config_dir / "test-users.json"
            if not users_file.exists():
                raise FileNotFoundError(f"Test users file not found: {users_file}")
            
            with open(users_file, 'r') as f:
                self._test_users = json.load(f)
        
        return self._test_users
    
    def load_environments(self) -> Dict[str, Any]:
        """Load environments configuration.
        
        Returns:
            Environments dictionary
            
        Raises:
            FileNotFoundError: If environments file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        if self._environments is None:
            env_file = self.config_dir / "environments.json"
            if not env_file.exists():
                # Fallback to config.json environments
                config = self.load_config()
                return config.get("environments", {})
            
            with open(env_file, 'r') as f:
                self._environments = json.load(f)
        
        return self._environments
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get test user by ID.
        
        Args:
            user_id: User ID (e.g., 'user1', 'user2')
            
        Returns:
            User dictionary or None if not found
        """
        users = self.load_test_users()
        for user in users.get("users", []):
            if user.get("id") == user_id:
                return user
        return None
    
    def get_environment(self, env_name: Optional[str] = None) -> Dict[str, Any]:
        """Get environment configuration.
        
        Args:
            env_name: Environment name (defaults to current environment)
            
        Returns:
            Environment configuration dictionary
        """
        if env_name is None:
            env_name = self._current_environment
        
        # Try environments.json first
        envs = self.load_environments()
        if env_name in envs:
            return envs[env_name]
        
        # Fallback to config.json
        config = self.load_config()
        envs = config.get("environments", {})
        return envs.get(env_name, {})
    
    def set_environment(self, env_name: str):
        """Set current environment.
        
        Args:
            env_name: Environment name (e.g., 'local', 'staging')
        """
        self._current_environment = env_name
    
    def get_test_settings(self) -> Dict[str, Any]:
        """Get test settings from config.
        
        Returns:
            Test settings dictionary
        """
        config = self.load_config()
        return config.get("testSettings", {})
    
    def get_wait_strategies(self) -> Dict[str, Any]:
        """Get wait strategies from config.
        
        Returns:
            Wait strategies dictionary
        """
        config = self.load_config()
        return config.get("waitStrategies", {})
    
    def get_execution_settings(self) -> Dict[str, Any]:
        """Get execution settings from config.
        
        Returns:
            Execution settings dictionary
        """
        config = self.load_config()
        return config.get("execution", {})
    
    def validate(self) -> bool:
        """Validate configuration files.
        
        Returns:
            True if valid, raises exception if invalid
        """
        # Load all configs (will raise exceptions if invalid)
        self.load_config()
        self.load_test_users()
        self.load_environments()
        
        # Validate required fields
        config = self.load_config()
        required_fields = ["project", "environments", "testSettings"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        return True


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get global config loader instance.
    
    Returns:
        ConfigLoader instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
