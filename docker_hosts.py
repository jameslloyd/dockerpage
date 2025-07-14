"""
Docker host configuration management module.
Handles loading, saving, and managing Docker host configurations.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# Global variables for host management
current_host_id = None

def load_docker_hosts():
    """Load Docker hosts configuration from JSON file."""
    config_path = 'docker_hosts.json'
    
    # Default configuration
    default_config = {
        'hosts': {
            'local': {
                'name': 'Local Docker',
                'host': 'unix:///var/run/docker.sock',
                'tls_verify': False,
                'cert_path': '',
                'description': 'Local Docker daemon',
                'default': True
            }
        },
        'current_host': 'local'
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Ensure required keys exist
            if 'hosts' not in config:
                config['hosts'] = default_config['hosts']
            if 'current_host' not in config:
                config['current_host'] = 'local'
                
            return config
        else:
            # Create default config file
            save_docker_hosts(default_config)
            return default_config
            
    except Exception as e:
        logger.error(f"Error loading Docker hosts config: {e}")
        return default_config

def save_docker_hosts(hosts_config):
    """Save Docker hosts configuration to JSON file."""
    try:
        with open('docker_hosts.json', 'w') as f:
            json.dump(hosts_config, f, indent=2)
        logger.info("Docker hosts configuration saved successfully")
    except Exception as e:
        logger.error(f"Error saving Docker hosts config: {e}")

def get_current_host_id():
    """Get the current active Docker host ID."""
    from flask import session
    
    global current_host_id
    if current_host_id is None:
        hosts_config = load_docker_hosts()
        current_host_id = session.get('current_host', hosts_config.get('current_host', 'local'))
    return current_host_id

def set_current_host_id(host_id):
    """Set the current active Docker host ID."""
    from flask import session
    
    global current_host_id, docker_client
    current_host_id = host_id
    session['current_host'] = host_id
    # Clear the cached client so it will reconnect to the new host
    try:
        from docker_client import clear_docker_client
        clear_docker_client()
    except ImportError:
        pass  # docker_client module may not be imported yet

def get_current_host_config():
    """Get the current host configuration."""
    hosts_config = load_docker_hosts()
    current_host_id = get_current_host_id()
    return hosts_config['hosts'].get(current_host_id, {})

def validate_host_config(host_data):
    """Validate host configuration data."""
    required_fields = ['id', 'name', 'host']
    
    # Check required fields
    for field in required_fields:
        if not host_data.get(field, '').strip():
            return False, f"Missing required field: {field}"
    
    # Validate host ID format
    host_id = host_data['id']
    if not host_id.replace('_', '').replace('-', '').isalnum():
        return False, "Host ID can only contain letters, numbers, hyphens, and underscores"
    
    return True, ""

def add_host(host_data):
    """Add a new Docker host configuration."""
    try:
        # Validate input
        is_valid, error_msg = validate_host_config(host_data)
        if not is_valid:
            return False, error_msg
        
        hosts_config = load_docker_hosts()
        host_id = host_data['id']
        
        # Check if host ID already exists
        if host_id in hosts_config['hosts']:
            return False, f"Host ID '{host_id}' already exists"
        
        # Add the new host
        hosts_config['hosts'][host_id] = {
            'name': host_data['name'].strip(),
            'host': host_data['host'].strip(),
            'tls_verify': host_data.get('tls_verify', False),
            'cert_path': host_data.get('cert_path', '').strip(),
            'description': host_data.get('description', '').strip(),
            'default': False
        }
        
        save_docker_hosts(hosts_config)
        return True, f"Docker host '{host_data['name']}' added successfully"
        
    except Exception as e:
        logger.error(f"Error adding host: {e}")
        return False, f"Error adding host: {str(e)}"

def update_host(host_id, host_data):
    """Update an existing Docker host configuration."""
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return False, "Host not found"
        
        # Update the host configuration
        hosts_config['hosts'][host_id].update({
            'name': host_data['name'].strip(),
            'host': host_data['host'].strip(),
            'tls_verify': host_data.get('tls_verify', False),
            'cert_path': host_data.get('cert_path', '').strip(),
            'description': host_data.get('description', '').strip()
        })
        
        save_docker_hosts(hosts_config)
        return True, f"Docker host '{host_data['name']}' updated successfully"
        
    except Exception as e:
        logger.error(f"Error updating host {host_id}: {e}")
        return False, f"Error updating host: {str(e)}"

def delete_host(host_id):
    """Delete a Docker host configuration."""
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return False, "Host not found"
        
        if host_id == 'local':
            return False, "Cannot delete the local Docker host"
        
        # Get host name for the response message
        host_name = hosts_config['hosts'][host_id].get('name', host_id)
        
        # Remove the host
        del hosts_config['hosts'][host_id]
        
        # If this was the current host, switch to local
        if hosts_config.get('current_host') == host_id:
            hosts_config['current_host'] = 'local'
            set_current_host_id('local')
        
        save_docker_hosts(hosts_config)
        return True, f"Docker host '{host_name}' deleted successfully"
        
    except Exception as e:
        logger.error(f"Error deleting host {host_id}: {e}")
        return False, f"Error deleting host: {str(e)}"

def switch_host(host_id):
    """Switch to a different Docker host."""
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return False, "Host not found"
        
        # Update current host
        hosts_config['current_host'] = host_id
        save_docker_hosts(hosts_config)
        set_current_host_id(host_id)
        
        host_name = hosts_config['hosts'][host_id].get('name', host_id)
        return True, f"Switched to Docker host '{host_name}'"
        
    except Exception as e:
        logger.error(f"Error switching to host {host_id}: {e}")
        return False, f"Error switching host: {str(e)}"
