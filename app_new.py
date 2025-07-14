"""
Docker Container Dashboard - Main Application
A Flask web application for managing and monitoring Docker containers across multiple hosts.
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, session

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Log environment variables for debugging
logger.info(f"ENABLE_STATS environment variable: '{os.getenv('ENABLE_STATS', 'false')}'")
stats_enabled = os.getenv('ENABLE_STATS', '').lower() == 'true'
logger.info(f"Stats collection enabled: {stats_enabled}")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# Import modules
from docker_client import get_docker_client
from docker_hosts import load_docker_hosts, get_current_host_id
from container_formatter import format_container_info, format_container_info_lightweight
from api_routes import (
    api_hosts, api_add_host, api_update_host, api_delete_host, 
    api_switch_host, api_test_host, api_containers, api_container_details,
    api_container_stats, api_unused_resources
)

@app.route('/')
def index():
    """Main dashboard page."""
    logger.info("Starting index route")
    
    # Get current host info
    hosts_config = load_docker_hosts()
    current_host_id = get_current_host_id()
    current_host = hosts_config['hosts'].get(current_host_id, {})
    
    client = get_docker_client()
    if not client:
        logger.error("Failed to get Docker client")
        return render_template('error.html', 
                             error=f"Unable to connect to Docker daemon on host '{current_host.get('name', current_host_id)}'. Make sure Docker is running and accessible.",
                             hosts_config=hosts_config,
                             current_host_id=current_host_id)
    
    try:
        logger.info("Getting container lists")
        # Get all containers (running and stopped)
        all_containers = client.containers.list(all=True)
        running_containers = client.containers.list()
        logger.info(f"Found {len(all_containers)} total containers, {len(running_containers)} running")
        
        # Format container information and group by status
        containers_by_status = {
            'running': [],
            'exited': [],
            'created': [],
            'paused': [],
            'other': []
        }
        
        logger.info("Processing container information")
        
        # Use lightweight formatting for faster initial load
        use_lightweight = os.getenv('FAST_INITIAL_LOAD', 'true').lower() == 'true'
        
        for i, container in enumerate(all_containers):
            logger.info(f"Processing container {i+1}/{len(all_containers)}: {container.name}")
            
            if use_lightweight:
                container_info = format_container_info_lightweight(container, current_host)
            else:
                container_info = format_container_info(container, current_host)
                
            status = container_info['status']
            
            if status in containers_by_status:
                containers_by_status[status].append(container_info)
            else:
                containers_by_status['other'].append(container_info)
        
        logger.info("Getting Docker system info")
        # Get Docker system info
        system_info = client.info()
        
        # Don't collect unused resources on initial load for better performance
        # They will be loaded asynchronously when the user clicks the tab
        
        logger.info("Preparing stats")
        stats = {
            'total_containers': len(all_containers),
            'running_containers': len(running_containers),
            'exited_containers': len(containers_by_status['exited']),
            'created_containers': len(containers_by_status['created']),
            'paused_containers': len(containers_by_status['paused']),
            'other_containers': len(containers_by_status['other']),
            'docker_version': system_info.get('ServerVersion', 'N/A'),
            'total_images': len(client.images.list()),
            'system_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        logger.info("Rendering template")
        return render_template('dashboard.html', 
                             containers_by_status=containers_by_status, 
                             stats=stats, 
                             hosturl=os.getenv('HOST_URL', 'http://localhost:5000'),
                             stats_enabled=stats_enabled,
                             hosts_config=hosts_config,
                             current_host_id=current_host_id,
                             current_host=current_host)
    
    except Exception as e:
        logger.error(f"Error retrieving container information: {e}")
        return render_template('error.html', 
                             error=str(e),
                             hosts_config=hosts_config,
                             current_host_id=current_host_id)

@app.route('/hosts')
def hosts_management():
    """Docker hosts management page."""
    hosts_config = load_docker_hosts()
    current_host_id = get_current_host_id()
    
    return render_template('hosts.html', 
                         hosts_config=hosts_config,
                         current_host_id=current_host_id)

@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        client = get_docker_client()
        if client:
            client.ping()
            return {'status': 'healthy', 'docker': 'connected'}, 200
        else:
            return {'status': 'unhealthy', 'docker': 'disconnected'}, 503
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 503

# Register API routes
app.route('/api/hosts', methods=['GET'])(api_hosts)
app.route('/api/hosts', methods=['POST'])(api_add_host)
app.route('/api/hosts/<host_id>', methods=['PUT'])(api_update_host)
app.route('/api/hosts/<host_id>', methods=['DELETE'])(api_delete_host)
app.route('/api/hosts/<host_id>/switch', methods=['POST'])(api_switch_host)
app.route('/api/hosts/<host_id>/test', methods=['POST'])(api_test_host)
app.route('/api/containers', methods=['GET'])(api_containers)
app.route('/api/containers/<container_id>', methods=['GET'])(api_container_details)
app.route('/api/containers/stats', methods=['GET'])(api_container_stats)
app.route('/api/unused-resources', methods=['GET'])(api_unused_resources)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    if debug:
        logger.info("Starting Flask app in debug mode")
        app.run(debug=True, host='0.0.0.0', port=port)
    else:
        logger.info(f"Starting Flask app on port {port}")
        app.run(debug=False, host='0.0.0.0', port=port)
