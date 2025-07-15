"""
Self-hosted applications management module.
Handles loading, saving, and managing self-hosted app configurations.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

def load_self_hosted_apps():
    """Load self-hosted apps configuration from JSON file."""
    config_path = 'data/self_hosted_apps.json'
    
    # Default configuration with some example apps
    default_config = {
        'apps': {}
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Ensure required keys exist
            if 'apps' not in config:
                config['apps'] = {}
                
            return config
        else:
            # Create default config file
            save_self_hosted_apps(default_config)
            return default_config
            
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing self-hosted apps JSON file: {e}")
        return default_config
    except Exception as e:
        logger.error(f"Error loading self-hosted apps configuration: {e}")
        return default_config

def save_self_hosted_apps(config):
    """Save self-hosted apps configuration to JSON file."""
    config_path = 'data/self_hosted_apps.json'
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Self-hosted apps configuration saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving self-hosted apps configuration: {e}")
        return False

def add_app(app_id, app_data):
    """Add a new self-hosted app."""
    try:
        config = load_self_hosted_apps()
        
        # Validate required fields
        required_fields = ['title', 'url']
        for field in required_fields:
            if field not in app_data or not app_data[field].strip():
                raise ValueError(f"Missing required field: {field}")
        
        # Set default icon if not provided
        if 'icon_url' not in app_data or not app_data['icon_url'].strip():
            app_data['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/default.png'
        
        # Add app to configuration
        config['apps'][app_id] = {
            'title': app_data['title'].strip(),
            'url': app_data['url'].strip(),
            'local_url': app_data.get('local_url', '').strip(),
            'icon_url': app_data['icon_url'].strip(),
            'description': app_data.get('description', '').strip(),
            'category': app_data.get('category', 'Other').strip()
        }
        
        if save_self_hosted_apps(config):
            logger.info(f"Added self-hosted app: {app_id}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error adding self-hosted app {app_id}: {e}")
        return False

def update_app(app_id, app_data):
    """Update an existing self-hosted app."""
    try:
        config = load_self_hosted_apps()
        
        if app_id not in config['apps']:
            raise ValueError(f"App {app_id} not found")
        
        # Validate required fields
        required_fields = ['title', 'url']
        for field in required_fields:
            if field not in app_data or not app_data[field].strip():
                raise ValueError(f"Missing required field: {field}")
        
        # Set default icon if not provided
        if 'icon_url' not in app_data or not app_data['icon_url'].strip():
            app_data['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/default.png'
        
        # Update app in configuration
        config['apps'][app_id] = {
            'title': app_data['title'].strip(),
            'url': app_data['url'].strip(),
            'local_url': app_data.get('local_url', '').strip(),
            'icon_url': app_data['icon_url'].strip(),
            'description': app_data.get('description', '').strip(),
            'category': app_data.get('category', 'Other').strip()
        }
        
        if save_self_hosted_apps(config):
            logger.info(f"Updated self-hosted app: {app_id}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error updating self-hosted app {app_id}: {e}")
        return False

def delete_app(app_id):
    """Delete a self-hosted app."""
    try:
        config = load_self_hosted_apps()
        
        if app_id not in config['apps']:
            raise ValueError(f"App {app_id} not found")
        
        del config['apps'][app_id]
        
        if save_self_hosted_apps(config):
            logger.info(f"Deleted self-hosted app: {app_id}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error deleting self-hosted app {app_id}: {e}")
        return False

def get_app(app_id):
    """Get a specific self-hosted app."""
    try:
        config = load_self_hosted_apps()
        return config['apps'].get(app_id)
    except Exception as e:
        logger.error(f"Error getting self-hosted app {app_id}: {e}")
        return None

def get_apps_by_category():
    """Get all self-hosted apps grouped by category."""
    try:
        config = load_self_hosted_apps()
        apps_by_category = {}
        
        for app_id, app_data in config['apps'].items():
            category = app_data.get('category', 'Other')
            if category not in apps_by_category:
                apps_by_category[category] = []
            
            app_data_with_id = app_data.copy()
            app_data_with_id['id'] = app_id
            apps_by_category[category].append(app_data_with_id)
        
        return apps_by_category
    except Exception as e:
        logger.error(f"Error getting apps by category: {e}")
        return {}
