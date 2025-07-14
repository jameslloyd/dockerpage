#!/usr/bin/env python3
"""
Docker Container Dashboard
A Flask web application that displays running Docker containers and their attributes.
"""

import docker
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from datetime import datetime
import logging, os, json
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log environment configuration
logger.info(f"ENABLE_STATS environment variable: '{os.getenv('ENABLE_STATS', 'not set')}'")
logger.info(f"Stats collection enabled: {os.getenv('ENABLE_STATS', '').lower() == 'true'}")

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'docker-dashboard-secret-key-change-me')

# Global Docker client instance
docker_client = None
current_host_id = None

# Docker host configuration file
HOSTS_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docker_hosts.json')

def load_docker_hosts():
    """Load Docker host configurations from file."""
    try:
        if os.path.exists(HOSTS_CONFIG_FILE):
            with open(HOSTS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default configuration
            default_hosts = {
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
            save_docker_hosts(default_hosts)
            return default_hosts
    except Exception as e:
        logger.error(f"Error loading Docker hosts configuration: {e}")
        return {
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

def save_docker_hosts(hosts_config):
    """Save Docker host configurations to file."""
    try:
        with open(HOSTS_CONFIG_FILE, 'w') as f:
            json.dump(hosts_config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving Docker hosts configuration: {e}")
        return False

def get_current_host_id():
    """Get the current active Docker host ID."""
    global current_host_id
    if current_host_id is None:
        hosts_config = load_docker_hosts()
        current_host_id = session.get('current_host', hosts_config.get('current_host', 'local'))
    return current_host_id

def set_current_host_id(host_id):
    """Set the current active Docker host ID."""
    global current_host_id, docker_client
    current_host_id = host_id
    session['current_host'] = host_id
    # Clear existing client to force reconnection
    docker_client = None

def get_docker_client(host_id=None):
    """Initialize Docker client with error handling and support for multiple hosts."""
    global docker_client
    
    if host_id is None:
        host_id = get_current_host_id()
    
    # Return existing client if it's for the same host and working
    if docker_client and current_host_id == host_id:
        try:
            # Test the connection with a simple API call
            docker_client.ping()
            return docker_client
        except Exception as e:
            logger.warning(f"Existing Docker client failed ping test: {e}. Reconnecting...")
            docker_client = None
    
    # Load host configuration
    hosts_config = load_docker_hosts()
    host_config = hosts_config['hosts'].get(host_id)
    
    if not host_config:
        logger.error(f"Host configuration not found for host_id: {host_id}")
        return None
    
    docker_host = host_config.get('host', 'unix:///var/run/docker.sock')
    docker_tls_verify = host_config.get('tls_verify', False)
    docker_cert_path = host_config.get('cert_path', '')
    
    logger.info(f"Connecting to Docker host '{host_config.get('name', host_id)}': {docker_host}")
    logger.info(f"TLS verification: {docker_tls_verify}")
    if docker_cert_path:
        logger.info(f"Certificate path: {docker_cert_path}")
    
    # Different connection methods to try
    connection_methods = []
    
    # Method 1: Use configured host settings
    if docker_tls_verify and docker_cert_path:
        # TLS connection with certificates
        connection_methods.append({
            'name': f'TLS connection to {docker_host}',
            'method': lambda: docker.DockerClient(
                base_url=docker_host,
                timeout=10,  # 10 second timeout
                tls=docker.tls.TLSConfig(
                    client_cert=(
                        os.path.join(docker_cert_path, 'cert.pem'),
                        os.path.join(docker_cert_path, 'key.pem')
                    ),
                    ca_cert=os.path.join(docker_cert_path, 'ca.pem'),
                    verify=True
                )
            )
        })
    else:
        # Non-TLS connection (local socket, insecure TCP, or SSH)
        connection_methods.append({
            'name': f'Direct connection to {docker_host}',
            'method': lambda: docker.DockerClient(base_url=docker_host, timeout=10)  # 10 second timeout
        })
    
    # Method 2: Fallback to environment variables if available
    if host_id == 'local' or docker_host.startswith('unix://'):
        connection_methods.append({
            'name': 'Default from_env',
            'method': lambda: docker.from_env()
        })
        
        # Method 3: Local unix socket fallbacks
        connection_methods.append({
            'name': 'Local Unix socket',
            'method': lambda: docker.DockerClient(base_url='unix:///var/run/docker.sock')
        })
        
        connection_methods.append({
            'name': 'Alternative Unix socket',
            'method': lambda: docker.DockerClient(base_url='unix://var/run/docker.sock')
        })
    
    for method_info in connection_methods:
        try:
            logger.info(f"Attempting Docker connection: {method_info['name']}...")
            client = method_info['method']()
            
            # Test the connection with a simple API call
            version_info = client.version()
            logger.info(f"Successfully connected to Docker using {method_info['name']}")
            logger.info(f"Docker version: {version_info.get('Version', 'Unknown')}")
            logger.info(f"Docker API version: {version_info.get('ApiVersion', 'Unknown')}")
            
            # Log some basic system info for remote connections
            try:
                system_info = client.info()
                logger.info(f"Docker system: {system_info.get('Name', 'Unknown')} ({system_info.get('OperatingSystem', 'Unknown')})")
                logger.info(f"Docker architecture: {system_info.get('Architecture', 'Unknown')}")
            except Exception as info_error:
                logger.debug(f"Could not get system info: {info_error}")
            
            # Store the client globally for reuse
            docker_client = client
            return client
            
        except Exception as e:
            logger.warning(f"Connection method '{method_info['name']}' failed: {e}")
            continue
    
    logger.error(f"All Docker connection methods failed for host {host_id}")
    return None

def format_container_info(container, current_host=None):
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
        # Also skip stats collection on initial page load for faster rendering
        stats_enabled = os.getenv('ENABLE_STATS', '').lower() == 'true'
        skip_stats = os.getenv('SKIP_INITIAL_STATS', 'true').lower() == 'true'
        
        if container.status == 'running':
            if not stats_enabled or skip_stats:
                logger.debug(f"Stats collection disabled or skipped for container {container.name}")
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
            
            # If no port mappings found, check for PORT label
            if not port_mappings:
                try:
                    labels = container.attrs['Config']['Labels'] or {}
                    port_label = labels.get('PORT') or labels.get('port')
                    if port_label:
                        port_mappings.append(f"{port_label} (host)")
                        container_info['ports'] = port_mappings
                except Exception:
                    pass
            
            # Build URL for first exposed port if container is running
            container_info['first_port_url'] = None
            if container.status == 'running':
                if first_host_port:
                    # Use mapped port
                    host_url = get_host_url_for_containers(current_host)
                    container_info['first_port_url'] = f"http://{host_url}:{first_host_port}"
                else:
                    # Check for PORT label for host network containers
                    try:
                        labels = container.attrs['Config']['Labels'] or {}
                        port_label = labels.get('PORT') or labels.get('port')
                        if port_label:
                            host_url = get_host_url_for_containers(current_host)
                            container_info['first_port_url'] = f"http://{host_url}:{port_label}"
                    except Exception as label_error:
                        logger.debug(f"Could not check PORT label for container {container.name}: {label_error}")
                
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

def format_container_info_lightweight(container, current_host=None):
    """Format basic container information for fast initial loading."""
    try:
        # Only collect essential information for initial display
        container_info = {
            'id': container.id[:12],
            'name': container.name,
            'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
            'status': container.status,
            'created': datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S'),
            'state': container.attrs['State']['Status'],
            'health': None,
            'memory_usage': "N/A",
            'memory_limit': "N/A",
            'cpu_percent': "N/A",
            'networks': [],
            'ports': [],
            'command': container.attrs['Config']['Cmd'],
            'environment': container.attrs['Config']['Env'][:5] if container.attrs['Config']['Env'] else [],
            'restart_policy': container.attrs['HostConfig']['RestartPolicy']['Name'],
            'labels': {},
            'icon_url': "https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png",
            'first_port_url': None
        }
        
        # Get basic health status if available (quick check)
        try:
            state = container.attrs.get('State', {})
            health = state.get('Health', {})
            if health:
                health_status = health.get('Status', '')
                if health_status:
                    container_info['health'] = health_status.lower()
        except Exception:
            pass
            
        # Get basic port mappings for URL building (essential for functionality)
        try:
            ports = container.attrs['NetworkSettings']['Ports']
            port_mappings = []
            first_host_port = None
            
            for container_port, host_info in ports.items():
                if host_info:
                    for mapping in host_info:
                        host_port = mapping['HostPort']
                        port_mappings.append(f"{host_port}:{container_port}")
                        if first_host_port is None:
                            first_host_port = host_port
                else:
                    port_mappings.append(container_port)
            
            container_info['ports'] = port_mappings
            
            # If no port mappings found, check for PORT label
            if not port_mappings:
                try:
                    labels = container.attrs['Config']['Labels'] or {}
                    port_label = labels.get('PORT') or labels.get('port')
                    if port_label:
                        port_mappings.append(f"{port_label} (host)")
                        container_info['ports'] = port_mappings
                except Exception:
                    pass
            
            # Build URL for first exposed port if container is running
            if container.status == 'running':
                if first_host_port:
                    # Use mapped port
                    host_url = get_host_url_for_containers(current_host)
                    container_info['first_port_url'] = f"http://{host_url}:{first_host_port}"
                else:
                    # Check for PORT label for host network containers
                    try:
                        labels = container.attrs['Config']['Labels'] or {}
                        port_label = labels.get('PORT') or labels.get('port')
                        if port_label:
                            host_url = get_host_url_for_containers(current_host)
                            container_info['first_port_url'] = f"http://{host_url}:{port_label}"
                    except Exception:
                        pass
                
        except Exception:
            pass
            
        # Get basic icon from labels (quick check)
        try:
            labels = container.attrs['Config']['Labels'] or {}
            icon_url = None
            icon_labels = ['icon', 'icon.url', 'app.icon', 'org.opencontainers.image.icon']
            
            for label_key in icon_labels:
                if label_key in labels and labels[label_key]:
                    icon_url = labels[label_key]
                    break
            
            if icon_url:
                container_info['icon_url'] = icon_url
                
        except Exception:
            pass
        
        return container_info
        
    except Exception as e:
        logger.error(f"Error formatting lightweight container info for {container.name}: {e}")
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
                             stats_enabled=os.getenv('ENABLE_STATS', '').lower() == 'true',
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
    current_host = hosts_config['hosts'].get(current_host_id, {})
    return render_template('hosts.html', 
                         hosts_config=hosts_config,
                         current_host_id=current_host_id,
                         current_host=current_host)

@app.route('/api/hosts', methods=['GET'])
def api_hosts():
    """API endpoint to get Docker hosts configuration."""
    hosts_config = load_docker_hosts()
    current_host_id = get_current_host_id()
    return jsonify({
        'hosts': hosts_config['hosts'],
        'current_host': current_host_id
    })

@app.route('/api/hosts', methods=['POST'])
def api_add_host():
    """API endpoint to add a new Docker host."""
    try:
        data = request.get_json()
        
        if not data or 'id' not in data or 'name' not in data or 'host' not in data:
            return jsonify({'error': 'Missing required fields: id, name, host'}), 400
        
        hosts_config = load_docker_hosts()
        
        # Validate host ID
        host_id = data['id'].strip()
        if not host_id or host_id in hosts_config['hosts']:
            return jsonify({'error': 'Host ID already exists or is empty'}), 400
        
        # Create new host configuration
        new_host = {
            'name': data['name'].strip(),
            'host': data['host'].strip(),
            'tls_verify': data.get('tls_verify', False),
            'cert_path': data.get('cert_path', '').strip(),
            'description': data.get('description', '').strip(),
            'default': False
        }
        
        # Add the new host
        hosts_config['hosts'][host_id] = new_host
        
        if save_docker_hosts(hosts_config):
            return jsonify({'success': True, 'message': 'Host added successfully'})
        else:
            return jsonify({'error': 'Failed to save host configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error adding Docker host: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hosts/<host_id>', methods=['PUT'])
def api_update_host(host_id):
    """API endpoint to update a Docker host."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return jsonify({'error': 'Host not found'}), 404
        
        # Update host configuration
        host_config = hosts_config['hosts'][host_id]
        if 'name' in data:
            host_config['name'] = data['name'].strip()
        if 'host' in data:
            host_config['host'] = data['host'].strip()
        if 'tls_verify' in data:
            host_config['tls_verify'] = bool(data['tls_verify'])
        if 'cert_path' in data:
            host_config['cert_path'] = data['cert_path'].strip()
        if 'description' in data:
            host_config['description'] = data['description'].strip()
        
        if save_docker_hosts(hosts_config):
            # Clear client cache if updating current host
            if host_id == get_current_host_id():
                global docker_client
                docker_client = None
            return jsonify({'success': True, 'message': 'Host updated successfully'})
        else:
            return jsonify({'error': 'Failed to save host configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error updating Docker host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hosts/<host_id>', methods=['DELETE'])
def api_delete_host(host_id):
    """API endpoint to delete a Docker host."""
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return jsonify({'error': 'Host not found'}), 404
        
        # Prevent deleting the last host
        if len(hosts_config['hosts']) == 1:
            return jsonify({'error': 'Cannot delete the last Docker host'}), 400
        
        # Prevent deleting the current host
        current_host_id = get_current_host_id()
        if host_id == current_host_id:
            return jsonify({'error': 'Cannot delete the currently active host. Switch to another host first.'}), 400
        
        # Delete the host
        del hosts_config['hosts'][host_id]
        
        if save_docker_hosts(hosts_config):
            return jsonify({'success': True, 'message': 'Host deleted successfully'})
        else:
            return jsonify({'error': 'Failed to save host configuration'}), 500
            
    except Exception as e:
        logger.error(f"Error deleting Docker host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hosts/<host_id>/switch', methods=['POST'])
def api_switch_host(host_id):
    """API endpoint to switch to a different Docker host."""
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return jsonify({'error': 'Host not found'}), 404
        
        # Test connection to the new host
        test_client = get_docker_client(host_id)
        if not test_client:
            return jsonify({'error': f'Unable to connect to Docker host {host_id}'}), 500
        
        # Switch to the new host
        set_current_host_id(host_id)
        hosts_config['current_host'] = host_id
        save_docker_hosts(hosts_config)
        
        return jsonify({'success': True, 'message': f'Switched to host {hosts_config["hosts"][host_id]["name"]}'})
        
    except Exception as e:
        logger.error(f"Error switching to Docker host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hosts/<host_id>/test', methods=['POST'])
def api_test_host(host_id):
    """API endpoint to test connection to a Docker host."""
    import time
    import threading
    import queue
    
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return jsonify({'error': 'Host not found'}), 404
        
        host_config = hosts_config['hosts'][host_id]
        
        def test_connection(result_queue):
            """Test connection in a separate thread with timeout"""
            try:
                # Get a fresh client specifically for testing
                docker_host = host_config.get('host', 'unix:///var/run/docker.sock')
                docker_tls_verify = host_config.get('tls_verify', False)
                docker_cert_path = host_config.get('cert_path', '')
                
                if docker_tls_verify and docker_cert_path:
                    client = docker.DockerClient(
                        base_url=docker_host,
                        timeout=5,  # Shorter timeout for testing
                        tls=docker.tls.TLSConfig(
                            client_cert=(
                                os.path.join(docker_cert_path, 'cert.pem'),
                                os.path.join(docker_cert_path, 'key.pem')
                            ),
                            ca_cert=os.path.join(docker_cert_path, 'ca.pem'),
                            verify=True
                        )
                    )
                else:
                    client = docker.DockerClient(base_url=docker_host, timeout=5)
                
                # Test basic connectivity
                version_info = client.version()
                system_info = client.info()
                
                result_queue.put({
                    'success': True,
                    'message': 'Connection successful',
                    'docker_version': version_info.get('Version', 'Unknown'),
                    'api_version': version_info.get('ApiVersion', 'Unknown'),
                    'system_name': system_info.get('Name', 'Unknown'),
                    'os': system_info.get('OperatingSystem', 'Unknown'),
                    'architecture': system_info.get('Architecture', 'Unknown'),
                    'containers': system_info.get('Containers', 0),
                    'images': system_info.get('Images', 0),
                    'host_url': docker_host
                })
                
            except Exception as e:
                result_queue.put({
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'host_url': docker_host
                })
        
        # Run connection test in a separate thread with timeout
        result_queue = queue.Queue()
        test_thread = threading.Thread(target=test_connection, args=(result_queue,))
        test_thread.daemon = True
        test_thread.start()
        
        # Wait for result with timeout
        try:
            result = result_queue.get(timeout=10)  # 10 second total timeout
            if result['success']:
                return jsonify(result)
            else:
                return jsonify({
                    'error': f"Connection failed: {result['error']}",
                    'details': {
                        'error_type': result.get('error_type', 'Unknown'),
                        'host_url': result.get('host_url', 'Unknown'),
                        'suggestion': get_connection_suggestion(result.get('error', ''))
                    }
                }), 500
        except queue.Empty:
            return jsonify({
                'error': 'Connection test timed out',
                'details': {
                    'timeout': '10 seconds',
                    'host_url': host_config.get('host', 'Unknown'),
                    'suggestion': 'Check if the Docker daemon is running and accessible'
                }
            }), 500
            
    except Exception as e:
        logger.error(f"Error testing Docker host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

def get_connection_suggestion(error_message):
    """Provide helpful suggestions based on the error message."""
    error_lower = error_message.lower()
    
    if 'connection refused' in error_lower:
        return 'Docker daemon may not be running or the port may be incorrect'
    elif 'timeout' in error_lower:
        return 'Network connectivity issue or Docker daemon is not responding'
    elif 'permission denied' in error_lower:
        return 'Check Docker socket permissions or TLS certificate configuration'
    elif 'no such file' in error_lower:
        return 'Docker socket path may be incorrect'
    elif 'certificate' in error_lower or 'tls' in error_lower:
        return 'Check TLS certificate configuration and paths'
    else:
        return 'Check Docker daemon configuration and network connectivity'

@app.route('/api/containers')
def api_containers():
    """API endpoint to get container information as JSON."""
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        containers = client.containers.list(all=True)
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        containers_info = [format_container_info(container, current_host) for container in containers]
        return jsonify(containers_info)
    except Exception as e:
        logger.error(f"Error in API endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint."""
    client = get_docker_client()
    current_host_id = get_current_host_id()
    hosts_config = load_docker_hosts()
    current_host = hosts_config['hosts'].get(current_host_id, {})
    
    if client:
        return jsonify({
            'status': 'healthy', 
            'docker_connected': True,
            'current_host': current_host.get('name', current_host_id),
            'host_id': current_host_id
        })
    else:
        return jsonify({
            'status': 'unhealthy', 
            'docker_connected': False,
            'current_host': current_host.get('name', current_host_id),
            'host_id': current_host_id,
            'error': f'Unable to connect to Docker host {current_host.get("name", current_host_id)}'
        }), 503

@app.route('/api/unused-resources')
def api_unused_resources():
    """API endpoint to get unused Docker resources as JSON."""
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        unused_resources = get_unused_docker_resources()
        return jsonify(unused_resources)
    except Exception as e:
        logger.error(f"Error in unused resources API endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/container/<container_id>/details')
def api_container_details(container_id):
    """API endpoint to get detailed container information on demand."""
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        container = client.containers.get(container_id)
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        container_info = format_container_info(container, current_host)
        return jsonify(container_info)
    except docker.errors.NotFound:
        return jsonify({'error': 'Container not found'}), 404
    except Exception as e:
        logger.error(f"Error getting container details for {container_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/containers/stats')
def api_container_stats():
    """API endpoint to get container stats for running containers."""
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        running_containers = client.containers.list()
        stats_data = {}
        
        # Temporarily enable stats collection for this API call
        for container in running_containers:
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
                
                # Wait for result with 1 second timeout
                try:
                    stats = result_queue.get(timeout=1)
                    if stats:
                        container_stats = {
                            'memory_usage': "N/A",
                            'memory_limit': "N/A",
                            'cpu_percent': "N/A"
                        }
                        
                        # Calculate memory usage
                        if 'memory' in stats and 'usage' in stats['memory']:
                            memory_usage = stats['memory']['usage'] / (1024 * 1024)  # Convert to MB
                            memory_limit = stats['memory']['limit'] / (1024 * 1024)  # Convert to MB
                            container_stats['memory_usage'] = f"{memory_usage:.1f} MB"
                            if memory_limit > 0:
                                container_stats['memory_limit'] = f"{memory_limit:.1f} MB"
                        
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
                                    container_stats['cpu_percent'] = f"{cpu_percent:.1f}%"
                        
                        stats_data[container.id] = container_stats
                
                except queue.Empty:
                    logger.debug(f"Stats collection timed out for container {container.name}")
                    
            except Exception as e:
                logger.debug(f"Could not get stats for container {container.name}: {e}")
                continue
        
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"Error in container stats API endpoint: {e}")
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

def get_host_url_for_containers(current_host):
    """Get the appropriate host URL for building container links based on current Docker host."""
    # If we're connected to a remote TCP host, use its IP address
    if current_host and current_host.get('host', '').startswith('tcp://'):
        tcp_host = current_host.get('host', '')
        try:
            # Extract IP address from tcp://ip:port format
            ip_address = tcp_host.split('://')[1].split(':')[0]
            return ip_address
        except (IndexError, AttributeError):
            pass
    
    # Fall back to HOST_URL environment variable for local or invalid configs
    host_url = os.getenv('HOST_URL', 'localhost')
    # Remove protocol if present, we'll add http://
    if host_url.startswith(('http://', 'https://')):
        host_url = host_url.split('://', 1)[1]
    return host_url


if __name__ == '__main__':
    app.run()
