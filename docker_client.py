"""
Docker client management module.
Handles Docker client connections and connection management.
"""

import docker
import docker.tls
import os
import logging

logger = logging.getLogger(__name__)

# Global Docker client cache
docker_client = None

def clear_docker_client():
    """Clear the cached Docker client to force reconnection."""
    global docker_client
    docker_client = None

def get_docker_client(host_id=None):
    """Get Docker client for the specified host (or current host if none specified)."""
    from docker_hosts import get_current_host_id, load_docker_hosts
    
    global docker_client
    
    if host_id is None:
        host_id = get_current_host_id()
    
    # Return cached client if it's for the same host
    current_cached_host = getattr(get_docker_client, '_cached_host_id', None)
    if docker_client and current_cached_host == host_id:
        return docker_client
    
    hosts_config = load_docker_hosts()
    host_config = hosts_config['hosts'].get(host_id, {})
    
    if not host_config:
        logger.error(f"Host configuration not found for {host_id}")
        return None
    
    docker_host = host_config.get('host', 'unix:///var/run/docker.sock')
    docker_tls_verify = host_config.get('tls_verify', False)
    docker_cert_path = host_config.get('cert_path', '')
    
    logger.info(f"Connecting to Docker host '{host_config.get('name', host_id)}': {docker_host}")
    logger.info(f"TLS verification: {docker_tls_verify}")
    
    # Clear any existing client
    docker_client = None
    
    try:
        if docker_tls_verify and docker_cert_path:
            logger.info(f"Using TLS with certificates from: {docker_cert_path}")
            logger.info("Attempting Docker connection: TLS connection...")
            
            client = docker.DockerClient(
                base_url=docker_host,
                timeout=10,
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
            logger.info(f"Attempting Docker connection: Direct connection to {docker_host}...")
            client = docker.DockerClient(base_url=docker_host, timeout=10)
        
        # Test the connection
        version_info = client.version()
        system_info = client.info()
        
        logger.info(f"Successfully connected to Docker using Direct connection to {docker_host}")
        logger.info(f"Docker version: {version_info.get('Version', 'Unknown')}")
        logger.info(f"Docker API version: {version_info.get('ApiVersion', 'Unknown')}")
        logger.info(f"Docker system: {system_info.get('Name', 'Unknown')} ({system_info.get('OperatingSystem', 'Unknown')})")
        logger.info(f"Docker architecture: {system_info.get('Architecture', 'Unknown')}")
        
        docker_client = client
        get_docker_client._cached_host_id = host_id
        return client
        
    except docker.errors.DockerException as e:
        logger.error(f"Docker connection failed for {docker_host}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error connecting to Docker: {e}")
    
    logger.error(f"All Docker connection methods failed for host {host_id}")
    return None

def test_docker_connection(host_config):
    """Test connection to a Docker host without caching the client."""
    import time
    import threading
    import queue
    
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
        return result
    except queue.Empty:
        return {
            'success': False,
            'error': 'Connection test timed out',
            'details': {
                'timeout': '10 seconds',
                'host_url': host_config.get('host', 'Unknown'),
                'suggestion': 'Check if the Docker daemon is running and accessible'
            }
        }

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
