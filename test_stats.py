#!/usr/bin/env python3
import os
import docker
import logging

# Set up environment
os.environ['DISABLE_STATS'] = 'true'

# Configure logging to see what's happening
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_stats_collection():
    print("=== Testing Stats Collection ===")
    print(f"DISABLE_STATS = {os.getenv('DISABLE_STATS')}")
    
    stats_disabled = os.getenv('DISABLE_STATS', '').lower() == 'true'
    print(f"Stats disabled: {stats_disabled}")
    
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        print(f"Found {len(containers)} containers")
        
        for container in containers[:2]:  # Test first 2 containers
            print(f"\nTesting container: {container.name}")
            print(f"Status: {container.status}")
            
            if container.status == 'running':
                if stats_disabled:
                    print("  Stats collection DISABLED - skipping")
                else:
                    print("  Stats collection ENABLED - attempting to get stats")
                    try:
                        stats = container.stats(stream=False)
                        print("  Stats collection SUCCESS")
                    except Exception as e:
                        print(f"  Stats collection FAILED: {e}")
            else:
                print("  Container not running - skipping stats")
                
    except Exception as e:
        print(f"Docker error: {e}")

if __name__ == "__main__":
    test_stats_collection()
