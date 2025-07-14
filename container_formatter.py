"""
Container information formatting module.
Handles formatting container data for display in the dashboard.
"""

import os
import logging
import queue
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

def format_container_info(container, current_host=None):
    """Format comprehensive container information."""
    from utils import get_host_url_for_containers
    
    logger.debug(f"Starting format_container_info for {container.name}")
    try:
        # Basic container information (always available)
        container_info = {
            'id': container.id[:12],
            'name': container.name,
            'status': container.status,
            'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
            'created': container.attrs['Created'],
            'state': container.attrs['State']
        }
        
        # Get network mode and command
        try:
            container_info['network_mode'] = container.attrs['HostConfig']['NetworkMode']
            container_info['command'] = ' '.join(container.attrs['Config']['Cmd']) if container.attrs['Config'].get('Cmd') else ''
        except (KeyError, TypeError):
            container_info['network_mode'] = 'unknown'
            container_info['command'] = ''
        
        # Get environment variables
        try:
            env_vars = container.attrs['Config']['Env'] or []
            container_info['env_vars'] = [env for env in env_vars if not env.startswith('PATH=')]
        except (KeyError, TypeError):
            container_info['env_vars'] = []
        
        # Get restart policy
        try:
            restart_policy = container.attrs['HostConfig']['RestartPolicy']
            container_info['restart_policy'] = restart_policy.get('Name', 'no')
        except (KeyError, TypeError):
            container_info['restart_policy'] = 'unknown'
        
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
                'net.unraid.docker.icon',
                'io.portainer.icon'
            ]
            
            for label_key in icon_labels:
                if label_key in labels and labels[label_key]:
                    icon_url = labels[label_key]
                    break
            
            if icon_url:
                container_info['icon_url'] = icon_url
            else:
                # Default icon based on image name
                image_name = container_info['image'].lower()
                if 'nginx' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/nginx.png'
                elif 'postgres' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/postgresql.png'
                elif 'mysql' in image_name or 'mariadb' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/mysql.png'
                elif 'redis' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/redis.png'
                elif 'mongo' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/mongodb.png'
                elif 'node' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/nodejs.png'
                elif 'python' in image_name:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/python.png'
                else:
                    container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png'
                    
        except Exception as label_error:
            logger.warning(f"Could not get labels for container {container.name}: {label_error}")
            container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png'
        
        # Get health status if available
        try:
            health = container.attrs['State'].get('Health', {})
            if health:
                container_info['health'] = health.get('Status', '').lower()
            else:
                container_info['health'] = None
        except Exception:
            container_info['health'] = None
        
        # Get container stats if enabled and container is running
        if container.status == 'running' and os.getenv('ENABLE_STATS', '').lower() == 'true':
            if not os.getenv('SKIP_INITIAL_STATS', 'true').lower() == 'true':
                try:
                    def get_stats(container, result_queue):
                        try:
                            stats = container.stats(stream=False)
                            result_queue.put(stats)
                        except Exception as e:
                            logger.debug(f"Could not get stats for {container.name}: {e}")
                            result_queue.put(None)
                    
                    # Use threading to prevent hanging
                    result_queue = queue.Queue()
                    stats_thread = threading.Thread(target=get_stats, args=(container, result_queue))
                    stats_thread.daemon = True
                    stats_thread.start()
                    
                    try:
                        stats = result_queue.get(timeout=2)  # 2 second timeout
                        if stats:
                            # CPU Usage
                            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                            if system_delta > 0:
                                cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100
                                container_info['cpu_percent'] = round(cpu_percent, 2)
                            else:
                                container_info['cpu_percent'] = 0.0
                            
                            # Memory Usage
                            memory_usage = stats['memory_stats']['usage']
                            memory_limit = stats['memory_stats']['limit']
                            container_info['memory_usage'] = memory_usage
                            container_info['memory_limit'] = memory_limit
                            container_info['memory_percent'] = round((memory_usage / memory_limit) * 100, 2)
                        else:
                            container_info['cpu_percent'] = 0.0
                            container_info['memory_usage'] = 0
                            container_info['memory_limit'] = 0
                            container_info['memory_percent'] = 0.0
                    except queue.Empty:
                        logger.debug(f"Stats timeout for container {container.name}")
                        container_info['cpu_percent'] = 0.0
                        container_info['memory_usage'] = 0
                        container_info['memory_limit'] = 0
                        container_info['memory_percent'] = 0.0
                        
                except Exception as stats_error:
                    logger.debug(f"Error getting stats for container {container.name}: {stats_error}")
                    container_info['cpu_percent'] = 0.0
                    container_info['memory_usage'] = 0
                    container_info['memory_limit'] = 0
                    container_info['memory_percent'] = 0.0
            else:
                # Skip stats collection on initial load
                container_info['cpu_percent'] = 0.0
                container_info['memory_usage'] = 0
                container_info['memory_limit'] = 0
                container_info['memory_percent'] = 0.0
        else:
            container_info['cpu_percent'] = 0.0
            container_info['memory_usage'] = 0
            container_info['memory_limit'] = 0
            container_info['memory_percent'] = 0.0
        
        logger.debug(f"Finished format_container_info for {container.name}")
        return container_info
        
    except Exception as e:
        logger.error(f"Error formatting container info for {container.name}: {e}")
        return {
            'id': container.id[:12] if hasattr(container, 'id') else 'unknown',
            'name': container.name if hasattr(container, 'name') else 'unknown',
            'status': 'error',
            'image': 'unknown',
            'error': str(e)
        }

def format_container_info_lightweight(container, current_host=None):
    """Format basic container information for fast initial loading."""
    from utils import get_host_url_for_containers
    
    try:
        # Only collect essential information for initial display
        container_info = {
            'id': container.id[:12],
            'name': container.name,
            'status': container.status,
            'image': container.image.tags[0] if container.image.tags else container.image.id[:12],
            'created': container.attrs['Created'],
            'state': container.attrs['State'],
            'first_port_url': None
        }
        
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
            else:
                container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png'
                
        except Exception:
            container_info['icon_url'] = 'https://cdn.jsdelivr.net/gh/selfhst/icons/png/docker.png'
        
        # Get health status if available
        try:
            health = container.attrs['State'].get('Health', {})
            container_info['health'] = health.get('Status', '').lower() if health else None
        except Exception:
            container_info['health'] = None
        
        # Set default stats (not collected for lightweight)
        container_info.update({
            'cpu_percent': 0.0,
            'memory_usage': 0,
            'memory_limit': 0,
            'memory_percent': 0.0,
            'env_vars': [],
            'labels': {},
            'network_mode': 'unknown',
            'command': '',
            'restart_policy': 'unknown'
        })
        
        return container_info
        
    except Exception as e:
        logger.error(f"Error in lightweight formatting for {container.name}: {e}")
        return {
            'id': container.id[:12] if hasattr(container, 'id') else 'unknown',
            'name': container.name if hasattr(container, 'name') else 'unknown',
            'status': 'error',
            'image': 'unknown',
            'error': str(e)
        }
