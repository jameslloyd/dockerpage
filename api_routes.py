"""
API routes module.
Contains all API endpoint functions for the Docker dashboard.
"""

import os
import logging
import queue
import threading
from datetime import datetime
from flask import jsonify, request

logger = logging.getLogger(__name__)

def api_hosts():
    """API endpoint to get all Docker hosts."""
    from docker_hosts import load_docker_hosts
    
    try:
        hosts_config = load_docker_hosts()
        return jsonify(hosts_config)
    except Exception as e:
        logger.error(f"Error in API endpoint: {e}")
        return jsonify({'error': str(e)}), 500

def api_add_host():
    """API endpoint to add a new Docker host."""
    from docker_hosts import add_host
    
    try:
        host_data = request.get_json()
        
        if not host_data:
            return jsonify({'error': 'No data provided'}), 400
        
        success, message = add_host(host_data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error adding host: {e}")
        return jsonify({'error': str(e)}), 500

def api_update_host(host_id):
    """API endpoint to update a Docker host."""
    from docker_hosts import update_host
    
    try:
        host_data = request.get_json()
        
        if not host_data:
            return jsonify({'error': 'No data provided'}), 400
        
        success, message = update_host(host_id, host_data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error updating host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_delete_host(host_id):
    """API endpoint to delete a Docker host."""
    from docker_hosts import delete_host
    
    try:
        success, message = delete_host(host_id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error deleting host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_switch_host(host_id):
    """API endpoint to switch to a different Docker host."""
    from docker_hosts import switch_host
    
    try:
        success, message = switch_host(host_id)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logger.error(f"Error switching to host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_test_host(host_id):
    """API endpoint to test connection to a Docker host."""
    from docker_hosts import load_docker_hosts
    from docker_client import test_docker_connection, get_connection_suggestion
    
    try:
        hosts_config = load_docker_hosts()
        
        if host_id not in hosts_config['hosts']:
            return jsonify({'error': 'Host not found'}), 404
        
        host_config = hosts_config['hosts'][host_id]
        result = test_docker_connection(host_config)
        
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
            
    except Exception as e:
        logger.error(f"Error testing Docker host {host_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_containers():
    """API endpoint to get all containers."""
    from docker_client import get_docker_client
    from docker_hosts import get_current_host_id, load_docker_hosts
    from container_formatter import format_container_info
    
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

def api_container_details(container_id):
    """API endpoint to get detailed information about a specific container."""
    from docker_client import get_docker_client
    from docker_hosts import get_current_host_id, load_docker_hosts
    from container_formatter import format_container_info
    import docker
    
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

def api_container_stats():
    """API endpoint to get real-time container statistics."""
    from docker_client import get_docker_client
    from docker_hosts import get_current_host_id, load_docker_hosts
    
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        running_containers = client.containers.list()
        stats_data = []
        
        def get_stats(container, result_queue):
            try:
                stats = container.stats(stream=False)
                
                # CPU Usage
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100
                else:
                    cpu_percent = 0.0
                
                # Memory Usage
                memory_usage = stats['memory_stats']['usage']
                memory_limit = stats['memory_stats']['limit']
                memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
                
                result_queue.put({
                    'id': container.id[:12],
                    'name': container.name,
                    'cpu_percent': round(cpu_percent, 2),
                    'memory_usage': memory_usage,
                    'memory_limit': memory_limit,
                    'memory_percent': round(memory_percent, 2)
                })
            except Exception as e:
                logger.debug(f"Could not get stats for {container.name}: {e}")
                result_queue.put({
                    'id': container.id[:12],
                    'name': container.name,
                    'cpu_percent': 0.0,
                    'memory_usage': 0,
                    'memory_limit': 0,
                    'memory_percent': 0.0,
                    'error': str(e)
                })
        
        # Use threading to get stats from multiple containers concurrently
        threads = []
        result_queues = []
        
        for container in running_containers:
            result_queue = queue.Queue()
            thread = threading.Thread(target=get_stats, args=(container, result_queue))
            thread.daemon = True
            threads.append(thread)
            result_queues.append(result_queue)
            thread.start()
        
        # Wait for all threads to complete with timeout
        for i, thread in enumerate(threads):
            thread.join(timeout=3)  # 3 second timeout per container
            try:
                stats = result_queues[i].get_nowait()
                stats_data.append(stats)
            except queue.Empty:
                # Thread timed out, add placeholder data
                container = running_containers[i]
                stats_data.append({
                    'id': container.id[:12],
                    'name': container.name,
                    'cpu_percent': 0.0,
                    'memory_usage': 0,
                    'memory_limit': 0,
                    'memory_percent': 0.0,
                    'error': 'Timeout'
                })
        
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"Error getting container stats: {e}")
        return jsonify({'error': str(e)}), 500

def api_unused_resources():
    """API endpoint to get unused Docker resources."""
    from docker_client import get_docker_client
    from docker_hosts import get_current_host_id, load_docker_hosts
    
    client = get_docker_client()
    if not client:
        current_host_id = get_current_host_id()
        hosts_config = load_docker_hosts()
        current_host = hosts_config['hosts'].get(current_host_id, {})
        return jsonify({'error': f'Unable to connect to Docker daemon on host {current_host.get("name", current_host_id)}'}), 500
    
    try:
        # Get unused images
        unused_images = []
        all_images = client.images.list()
        used_images = set()
        
        # Get images used by containers
        for container in client.containers.list(all=True):
            used_images.add(container.image.id)
        
        for image in all_images:
            if image.id not in used_images and image.tags:  # Only show tagged images
                size_mb = round(image.attrs['Size'] / 1024 / 1024, 2)
                unused_images.append({
                    'id': image.id[:12],
                    'tags': image.tags,
                    'size': f"{size_mb} MB",
                    'created': image.attrs['Created']
                })
        
        # Get unused volumes
        unused_volumes = []
        all_volumes = client.volumes.list()
        used_volumes = set()
        
        # Get volumes used by containers
        for container in client.containers.list(all=True):
            mounts = container.attrs.get('Mounts', [])
            for mount in mounts:
                if mount.get('Type') == 'volume':
                    used_volumes.add(mount.get('Name'))
        
        for volume in all_volumes:
            if volume.name not in used_volumes:
                unused_volumes.append({
                    'name': volume.name,
                    'driver': volume.attrs.get('Driver', 'unknown'),
                    'created': volume.attrs.get('CreatedAt', 'unknown')
                })
        
        # Get unused networks
        unused_networks = []
        all_networks = client.networks.list()
        used_networks = set(['bridge', 'host', 'none'])  # System networks
        
        # Get networks used by containers
        for container in client.containers.list(all=True):
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            for network_name in networks.keys():
                used_networks.add(network_name)
        
        for network in all_networks:
            if network.name not in used_networks:
                unused_networks.append({
                    'id': network.id[:12],
                    'name': network.name,
                    'driver': network.attrs.get('Driver', 'unknown'),
                    'created': network.attrs.get('Created', 'unknown')
                })
        
        return jsonify({
            'images': unused_images,
            'volumes': unused_volumes,
            'networks': unused_networks
        })
        
    except Exception as e:
        logger.error(f"Error getting unused resources: {e}")
        return jsonify({'error': str(e)}), 500

# Import for self-hosted apps
from self_hosted_apps import (
    load_self_hosted_apps, add_app, update_app, delete_app, 
    get_app, get_apps_by_category
)

def api_self_hosted_apps():
    """Get all self-hosted apps."""
    try:
        config = load_self_hosted_apps()
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting self-hosted apps: {e}")
        return jsonify({'error': str(e)}), 500

def api_add_self_hosted_app():
    """Add a new self-hosted app."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Generate app ID from title
        app_id = data.get('title', '').lower().replace(' ', '_').replace('-', '_')
        app_id = ''.join(c for c in app_id if c.isalnum() or c == '_')
        
        if not app_id:
            return jsonify({'error': 'Invalid title for app ID generation'}), 400
        
        # Check if app already exists
        existing_config = load_self_hosted_apps()
        if app_id in existing_config['apps']:
            return jsonify({'error': f'App with ID {app_id} already exists'}), 409
        
        if add_app(app_id, data):
            return jsonify({'message': 'App added successfully', 'app_id': app_id}), 201
        else:
            return jsonify({'error': 'Failed to add app'}), 500
            
    except Exception as e:
        logger.error(f"Error adding self-hosted app: {e}")
        return jsonify({'error': str(e)}), 500

def api_update_self_hosted_app(app_id):
    """Update an existing self-hosted app."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if update_app(app_id, data):
            return jsonify({'message': 'App updated successfully'}), 200
        else:
            return jsonify({'error': 'Failed to update app'}), 500
            
    except Exception as e:
        logger.error(f"Error updating self-hosted app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_delete_self_hosted_app(app_id):
    """Delete a self-hosted app."""
    try:
        if delete_app(app_id):
            return jsonify({'message': 'App deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete app'}), 500
            
    except Exception as e:
        logger.error(f"Error deleting self-hosted app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500

def api_get_self_hosted_app(app_id):
    """Get a specific self-hosted app."""
    try:
        app = get_app(app_id)
        if app:
            app_with_id = app.copy()
            app_with_id['id'] = app_id
            return jsonify(app_with_id), 200
        else:
            return jsonify({'error': 'App not found'}), 404
            
    except Exception as e:
        logger.error(f"Error getting self-hosted app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500
