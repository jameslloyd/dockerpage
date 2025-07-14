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
logger.info(f"ENABLE_STATS environment variable: '{os.getenv('ENABLE_STATS', 'not set')}'")
logger.info(f"Stats collection enabled: {os.getenv('ENABLE_STATS', '').lower() == 'true'}")

app = Flask(__name__)

# Global Docker client instance
docker_client = None

def get_docker_client():
    """Initialize Docker client with error handling and multiple connection methods."""
    global docker_client
    
    # Return existing client if available and working
    if docker_client:
        try:
            # Test the connection with a simple API call
            docker_client.ping()
            return docker_client
        except Exception as e:
            logger.warning(f"Existing Docker client failed ping test: {e}. Reconnecting...")
            docker_client = None
    
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
            
            # Store the client globally for reuse
            docker_client = client
            return client
            
        except Exception as e:
            logger.warning(f"Connection method '{method_info['name']}' failed: {e}")
            continue
    
    logger.error("All Docker connection methods failed")
    return None

def format_container_info(container):
    """Format container information for display."""
    logger.debug(f"Starting format_container_info for {container.name}")
    try:
        # Basic container information (always available)
        container_info = {
            'id': container.id[:12],
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
            'status': container.status,
            'created': datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S'),
            'state': container.attrs['State']['Status'],
            'health': None,  # Will be populated below if available
            'memory_usage': "N/A",
            'memory_limit': "N/A",
            'cpu_percent': "N/A",
            'networks': [],
            'ports': [],
            'command': container.attrs['Config']['Cmd'],
            'environment': container.attrs['Config']['Env'][:5] if container.attrs['Config']['Env'] else [],
            'restart_policy': container.attrs['HostConfig']['RestartPolicy']['Name']
        }
        
        logger.debug(f"Basic info collected for {container.name}")
        
        # Get health status if available
        try:
            state = container.attrs.get('State', {})
            health = state.get('Health', {})
            if health:
                health_status = health.get('Status', '')
                if health_status:
                    container_info['health'] = health_status.lower()
        except Exception as health_error:
            logger.debug(f"Could not get health info for container {container.name}: {health_error}")
        
        logger.debug(f"Health info collected for {container.name}")
        
        # Only get stats for running containers if stats collection is enabled
        # Stats collection can be disabled via DISABLE_STATS=true environment variable
        # For better performance, we now default to disabled stats unless explicitly enabled
        stats_enabled = os.getenv('ENABLE_STATS', '').lower() == 'true'
        
        if container.status == 'running':
            if not stats_enabled:
                logger.debug(f"Stats collection disabled for container {container.name}")
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
                    
                    # Wait for result with 1 second timeout (reduced from 2 seconds)
                    try:
                        stats = result_queue.get(timeout=1)
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
        
        # Get port mappings and build first port URL
        try:
            ports = container.attrs['NetworkSettings']['Ports']
            port_mappings = []
            first_host_port = None
            
            for container_port, host_info in ports.items():
                if host_info:
                    for mapping in host_info:
                        host_port = mapping['HostPort']
                        port_mappings.append(f"{host_port}:{container_port}")
                        # Capture the first mapped port for URL building
                        if first_host_port is None:
                            first_host_port = host_port
                else:
                    port_mappings.append(container_port)
            
            container_info['ports'] = port_mappings
            
            # Build URL for first exposed port if container is running
            container_info['first_port_url'] = None
            if container.status == 'running' and first_host_port:
                host_url = os.getenv('HOST_URL', 'localhost')
                # Remove protocol if present, we'll add http://
                if host_url.startswith(('http://', 'https://')):
                    host_url = host_url.split('://', 1)[1]
                container_info['first_port_url'] = f"http://{host_url}:{first_host_port}"
                
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
    logger.info("Starting index route")
    client = get_docker_client()
    if not client:
        logger.error("Failed to get Docker client")
        return render_template('error.html', 
                             error="Unable to connect to Docker daemon. Make sure Docker is running and accessible.")
    
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
        for i, container in enumerate(all_containers):
            logger.info(f"Processing container {i+1}/{len(all_containers)}: {container.name}")
            container_info = format_container_info(container)
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
                             hosturl=os.getenv('HOST_URL', 'http://localhost:5000'))
    
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

@app.route('/api/unused-resources')
def api_unused_resources():
    """API endpoint to get unused Docker resources as JSON."""
    client = get_docker_client()
    if not client:
        return jsonify({'error': 'Unable to connect to Docker daemon'}), 500
    
    try:
        unused_resources = get_unused_docker_resources()
        return jsonify(unused_resources)
    except Exception as e:
        logger.error(f"Error in unused resources API endpoint: {e}")
        return jsonify({'error': str(e)}), 500

def get_unused_docker_resources():
    """Get information about unused Docker resources."""
    client = get_docker_client()
    if not client:
        return {
            'volumes': [],
            'images': [],
            'networks': [],
            'error': 'Unable to connect to Docker daemon'
        }
    
    try:
        unused_resources = {
            'volumes': [],
            'images': [],
            'networks': []
        }
        
        # Get unused volumes
        try:
            all_volumes = client.volumes.list()
            containers = client.containers.list(all=True)
            
            # Get volumes used by containers
            used_volumes = set()
            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume' and mount.get('Name'):
                        used_volumes.add(mount['Name'])
            
            # Find unused volumes
            for volume in all_volumes:
                if volume.name not in used_volumes:
                    try:
                        volume_info = {
                            'name': volume.name,
                            'driver': volume.attrs.get('Driver', 'N/A'),
                            'mountpoint': volume.attrs.get('Mountpoint', 'N/A'),
                            'created': volume.attrs.get('CreatedAt', 'N/A'),
                            'size': 'Unknown',  # Size calculation would require additional API calls
                            'labels': volume.attrs.get('Labels') or {}
                        }
                        unused_resources['volumes'].append(volume_info)
                    except Exception as e:
                        logger.warning(f"Error getting volume info for {volume.name}: {e}")
                        
        except Exception as e:
            logger.error(f"Error getting unused volumes: {e}")
        
        # Get unused images (dangling images)
        try:
            all_images = client.images.list(all=True)
            containers = client.containers.list(all=True)
            
            # Get images used by containers
            used_images = set()
            for container in containers:
                image_id = container.attrs.get('Image', '')
                if image_id:
                    used_images.add(image_id)
                # Also add the image name/tag if available
                image_name = container.attrs.get('Config', {}).get('Image', '')
                if image_name:
                    used_images.add(image_name)
            
            # Find unused images (excluding base images and images with tags)
            for image in all_images:
                # Skip images that are being used
                is_used = False
                for used_img in used_images:
                    if used_img in [image.id, image.short_id] or any(used_img in tag for tag in image.tags):
                        is_used = True
                        break
                
                if not is_used:
                    try:
                        # Calculate image size
                        size_mb = image.attrs.get('Size', 0) / (1024 * 1024)
                        
                        image_info = {
                            'id': image.short_id,
                            'tags': image.tags if image.tags else ['<none>:<none>'],
                            'created': image.attrs.get('Created', 'N/A'),
                            'size': f"{size_mb:.1f} MB" if size_mb > 0 else 'Unknown',
                            'dangling': len(image.tags) == 0
                        }
                        unused_resources['images'].append(image_info)
                    except Exception as e:
                        logger.warning(f"Error getting image info for {image.short_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error getting unused images: {e}")
        
        # Get unused networks (networks with no containers)
        try:
            all_networks = client.networks.list()
            containers = client.containers.list(all=True)
            
            # Get networks used by containers
            used_networks = set()
            for container in containers:
                networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
                for network_name in networks.keys():
                    used_networks.add(network_name)
            
            # Default networks that should not be considered for removal
            default_networks = {'bridge', 'host', 'none'}
            
            for network in all_networks:
                if (network.name not in used_networks and 
                    network.name not in default_networks and
                    network.attrs.get('Scope') != 'swarm'):
                    try:
                        network_info = {
                            'id': network.short_id,
                            'name': network.name,
                            'driver': network.attrs.get('Driver', 'N/A'),
                            'scope': network.attrs.get('Scope', 'N/A'),
                            'created': network.attrs.get('Created', 'N/A'),
                            'labels': network.attrs.get('Labels') or {}
                        }
                        unused_resources['networks'].append(network_info)
                    except Exception as e:
                        logger.warning(f"Error getting network info for {network.name}: {e}")
                        
        except Exception as e:
            logger.error(f"Error getting unused networks: {e}")
        
        return unused_resources
        
    except Exception as e:
        logger.error(f"Error getting unused Docker resources: {e}")
        return {
            'volumes': [],
            'images': [],
            'networks': [],
            'error': str(e)
        }
