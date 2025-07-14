"""
Docker Container Dashboard - Main Application
A Flask web application for managing and monitoring Docker containers across multiple hosts.
"""

import os
import logging
from datetime import datetime
from flask import Flask, render_template, session

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'WARN').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Configure werkzeug logger to respect the same log level
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(getattr(logging, log_level, logging.INFO))

# Also configure Flask's logger
flask_logger = logging.getLogger('flask')
flask_logger.setLevel(getattr(logging, log_level, logging.INFO))

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
    """Main dashboard page showing containers from all configured hosts."""
    logger.info("Starting index route")
    
    # Get host configurations
    hosts_config = load_docker_hosts()
    current_host_id = get_current_host_id()
    
    # Get containers from all hosts
    all_hosts_data = {}
    global_stats = {
        'total_containers': 0,
        'running_containers': 0,
        'exited_containers': 0,
        'created_containers': 0,
        'paused_containers': 0,
        'other_containers': 0,
        'total_images': 0,
        'connected_hosts': 0,
        'total_hosts': len(hosts_config['hosts']),
        'system_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Use lightweight formatting for faster initial load
    use_lightweight = os.getenv('FAST_INITIAL_LOAD', 'true').lower() == 'true'
    
    # Iterate through all configured hosts
    for host_id, host_config in hosts_config['hosts'].items():
        logger.info(f"Getting containers from host: {host_config.get('name', host_id)}")
        
        # Initialize host data structure
        host_data = {
            'config': host_config,
            'connected': False,
            'error': None,
            'containers_by_status': {
                'running': [],
                'exited': [],
                'created': [],
                'paused': [],
                'other': []
            },
            'stats': {
                'total_containers': 0,
                'running_containers': 0,
                'exited_containers': 0,
                'created_containers': 0,
                'paused_containers': 0,
                'other_containers': 0,
                'total_images': 0,
                'docker_version': 'N/A'
            }
        }
        
        try:
            # Get Docker client for this specific host
            client = get_docker_client(host_id)
            if not client:
                host_data['error'] = "Unable to connect to Docker daemon"
                logger.warning(f"Failed to connect to host {host_id}")
                all_hosts_data[host_id] = host_data
                continue
            
            # Test connection and get system info
            system_info = client.info()
            host_data['connected'] = True
            global_stats['connected_hosts'] += 1
            
            # Get all containers (running and stopped)
            all_containers = client.containers.list(all=True)
            running_containers = client.containers.list()
            
            logger.info(f"Host {host_id}: Found {len(all_containers)} total containers, {len(running_containers)} running")
            
            # Process container information
            for i, container in enumerate(all_containers):
                if use_lightweight:
                    container_info = format_container_info_lightweight(container, host_config)
                else:
                    container_info = format_container_info(container, host_config)
                
                # Add host information to container
                container_info['host_id'] = host_id
                container_info['host_name'] = host_config.get('name', host_id)
                
                status = container_info['status']
                if status in host_data['containers_by_status']:
                    host_data['containers_by_status'][status].append(container_info)
                else:
                    host_data['containers_by_status']['other'].append(container_info)
            
            # Update host stats
            host_data['stats'] = {
                'total_containers': len(all_containers),
                'running_containers': len(running_containers),
                'exited_containers': len(host_data['containers_by_status']['exited']),
                'created_containers': len(host_data['containers_by_status']['created']),
                'paused_containers': len(host_data['containers_by_status']['paused']),
                'other_containers': len(host_data['containers_by_status']['other']),
                'total_images': len(client.images.list()),
                'docker_version': system_info.get('ServerVersion', 'N/A')
            }
            
            # Update global stats
            global_stats['total_containers'] += host_data['stats']['total_containers']
            global_stats['running_containers'] += host_data['stats']['running_containers']
            global_stats['exited_containers'] += host_data['stats']['exited_containers']
            global_stats['created_containers'] += host_data['stats']['created_containers']
            global_stats['paused_containers'] += host_data['stats']['paused_containers']
            global_stats['other_containers'] += host_data['stats']['other_containers']
            global_stats['total_images'] += host_data['stats']['total_images']
            
        except Exception as e:
            logger.error(f"Error retrieving container information from host {host_id}: {e}")
            host_data['error'] = str(e)
        
        all_hosts_data[host_id] = host_data
    
    # If no hosts are connected, show error
    if global_stats['connected_hosts'] == 0:
        return render_template('error.html', 
                             error="Unable to connect to any configured Docker hosts. Please check your host configurations.",
                             hosts_config=hosts_config,
                             current_host_id=current_host_id)
    
    logger.info("Rendering multi-host dashboard template")
    return render_template('dashboard.html', 
                         all_hosts_data=all_hosts_data,
                         global_stats=global_stats,
                         hosturl=os.getenv('HOST_URL', 'http://localhost:5000'),
                         stats_enabled=stats_enabled,
                         hosts_config=hosts_config,
                         current_host_id=current_host_id,
                         multi_host_view=True)

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
