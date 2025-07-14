#!/usr/bin/env python3
"""
Docker Container Dashboard
A Flask web application that displays running Docker containers and their attributes.
"""

import docker
from flask import Flask, render_template, jsonify
from datetime import datetime
import logging, os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log environment configuration
logger.info(f"DISABLE_STATS environment variable: '{os.getenv('DISABLE_STATS', 'not set')}'")
logger.info(f"Stats collection enabled: {not os.getenv('DISABLE_STATS', '').lower() == 'true'}")

app = Flask(__name__)

def get_docker_client():
    """Initialize Docker client with error handling and multiple connection methods."""
    import os
    
    # Different connection methods to try
    connection_methods = [
        # Method 1: Direct unix socket connection
        {'name': 'Unix socket', 'method': lambda: docker.DockerClient(base_url='unix:///var/run/docker.sock')},
        
        # Method 2: Environment-based connection with explicit base URL
        {'name': 'Environment with socket', 'method': lambda: docker.DockerClient(base_url='unix://var/run/docker.sock')},
        
        # Method 3: Default from_env method
        {'name': 'Default from_env', 'method': lambda: docker.from_env()},
        
        # Method 4: TCP connection if DOCKER_HOST is set
        {'name': 'TCP connection', 'method': lambda: docker.DockerClient(base_url=os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock'))},
    ]
    
    for method_info in connection_methods:
        try:
            logger.info(f"Attempting Docker connection: {method_info['name']}...")
            client = method_info['method']()
            
            # Test the connection with a simple API call
            version_info = client.version()
            logger.info(f"Successfully connected to Docker using {method_info['name']}")
            logger.info(f"Docker version: {version_info.get('Version', 'Unknown')}")
            return client
            
        except Exception as e:
            logger.warning(f"Connection method '{method_info['name']}' failed: {e}")
            continue
    
    logger.error("All Docker connection methods failed")
    return None

def format_container_info(container):
    """Format container information for display."""
    try:
        # Basic container information (always available)
        container_info = {
            'id': container.id[:12],
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
            'status': container.status,
            'created': datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S'),
            'state': container.attrs['State']['Status'],
            'memory_usage': "N/A",
            'memory_limit': "N/A",
            'cpu_percent': "N/A",
            'networks': [],
            'ports': [],
            'command': container.attrs['Config']['Cmd'],
            'environment': container.attrs['Config']['Env'][:5] if container.attrs['Config']['Env'] else [],
            'restart_policy': container.attrs['HostConfig']['RestartPolicy']['Name']
        }
        
        # Only get stats for running containers if stats collection is enabled
        # Stats collection can be disabled via DISABLE_STATS=true environment variable
        stats_disabled = os.getenv('DISABLE_STATS', '').lower() == 'true'
        
        if container.status == 'running':
            if stats_disabled:
                logger.info(f"Stats collection disabled for container {container.name}")
            else:
                try:
                    import threading
                    import queue
                    
                    def get_stats(container, result_queue):
                        """Get container stats in a separate thread"""
                        try:
                            stats = container.stats(stream=False)
                            result_queue.put(stats)
                        except Exception as e:
                            result_queue.put(None)
                    
                    # Use threading with timeout to prevent hanging
                    result_queue = queue.Queue()
                    stats_thread = threading.Thread(target=get_stats, args=(container, result_queue))
                    stats_thread.daemon = True
                    stats_thread.start()
                    
                    # Wait for result with 2 second timeout
                    try:
                        stats = result_queue.get(timeout=2)
                        if stats:
                            # Calculate memory usage
                            if 'memory' in stats and 'usage' in stats['memory']:
                                memory_usage = stats['memory']['usage'] / (1024 * 1024)  # Convert to MB
                                memory_limit = stats['memory']['limit'] / (1024 * 1024)  # Convert to MB
                                container_info['memory_usage'] = f"{memory_usage:.1f} MB"
                                if memory_limit > 0:
                                    container_info['memory_limit'] = f"{memory_limit:.1f} MB"
                            
                            # Calculate CPU usage
                            if 'cpu_stats' in stats and 'precpu_stats' in stats:
                                cpu_stats = stats['cpu_stats']
                                precpu_stats = stats['precpu_stats']
                                
                                if ('cpu_usage' in cpu_stats and 'cpu_usage' in precpu_stats and
                                    'total_usage' in cpu_stats['cpu_usage'] and 'total_usage' in precpu_stats['cpu_usage']):
                                    cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                                    system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                                    
                                    if system_delta > 0:
                                        cpu_percent = (cpu_delta / system_delta) * len(cpu_stats['cpu_usage']['percpu_usage']) * 100
                                        container_info['cpu_percent'] = f"{cpu_percent:.1f}%"
                    
                    except queue.Empty:
                        logger.debug(f"Stats collection timed out for container {container.name}")
                                
                except Exception as stats_error:
                    logger.debug(f"Could not get stats for container {container.name}: {stats_error}")
                    # Continue without stats - this is not critical
        
        # Get network information
        try:
            networks = container.attrs['NetworkSettings']['Networks']
            network_info = []
            for network_name, network_data in networks.items():
                network_info.append({
                    'name': network_name,
                    'ip': network_data.get('IPAddress', 'N/A')
                })
            container_info['networks'] = network_info
        except Exception as network_error:
            logger.warning(f"Could not get network info for container {container.name}: {network_error}")
        
        # Get port mappings
        try:
            ports = container.attrs['NetworkSettings']['Ports']
            port_mappings = []
            for container_port, host_info in ports.items():
                if host_info:
                    for mapping in host_info:
                        port_mappings.append(f"{mapping['HostPort']}:{container_port}")
                else:
                    port_mappings.append(container_port)
            container_info['ports'] = port_mappings
        except Exception as port_error:
            logger.warning(f"Could not get port info for container {container.name}: {port_error}")
        
        # Get container labels and extract icon information
        try:
            labels = container.attrs['Config']['Labels'] or {}
            container_info['labels'] = labels
            
            # Look for icon URL in various common label formats
            icon_url = None
            icon_labels = [
                'icon',
                'icon.url', 
                'app.icon',
                'org.opencontainers.image.icon',
                'traefik.http.routers.icon',
                'homepage.icon',
                'diun.watch.repo.icon'
            ]
            
            for label_key in icon_labels:
                if label_key in labels and labels[label_key]:
                    icon_url = labels[label_key]
                    break
            
            # Use default Docker icon if no icon label is found
            if not icon_url:
                icon_url = "https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png"
            
            container_info['icon_url'] = icon_url
            
        except Exception as label_error:
            logger.warning(f"Could not get labels for container {container.name}: {label_error}")
            container_info['labels'] = {}
            container_info['icon_url'] = "https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png"
        
        return container_info
        
    except Exception as e:
        logger.error(f"Error formatting container info for {container.name}: {e}")
        return {
            'id': container.id[:12],
            'name': container.name,
            'image': 'N/A',
            'status': container.status,
            'error': str(e)
        }

@app.route('/')
def index():
    """Main dashboard page."""
    client = get_docker_client()
    if not client:
        return render_template('error.html', 
                             error="Unable to connect to Docker daemon. Make sure Docker is running and accessible.")
    
    try:
        # Get all containers (running and stopped)
        all_containers = client.containers.list(all=True)
        running_containers = client.containers.list()
        
        # Format container information and group by status
        containers_by_status = {
            'running': [],
            'exited': [],
            'created': [],
            'paused': [],
            'other': []
        }
        
        for container in all_containers:
            container_info = format_container_info(container)
            status = container_info['status']
            
            if status in containers_by_status:
                containers_by_status[status].append(container_info)
            else:
                containers_by_status['other'].append(container_info)
        
        # Get Docker system info
        system_info = client.info()
        
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
        
        return render_template('dashboard.html', containers_by_status=containers_by_status, stats=stats, hosturl=os.getenv('HOST_URL', 'http://localhost:5000'))
    
    except Exception as e:
        logger.error(f"Error retrieving container information: {e}")
        return render_template('error.html', error=str(e))

@app.route('/api/containers')
def api_containers():
    """API endpoint to get container information as JSON."""
    client = get_docker_client()
    if not client:
        return jsonify({'error': 'Unable to connect to Docker daemon'}), 500
    
    try:
        containers = client.containers.list(all=True)
        containers_info = [format_container_info(container) for container in containers]
        return jsonify(containers_info)
    except Exception as e:
        logger.error(f"Error in API endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint."""
    client = get_docker_client()
    if client:
        return jsonify({'status': 'healthy', 'docker_connected': True})
    else:
        return jsonify({'status': 'unhealthy', 'docker_connected': False}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
