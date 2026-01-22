import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

def check_ping(hostname):
    """
    Pings a host to check if it's online.
    Returns True if online, False if offline.
    """
    if not hostname:
        return False

    # Determine command based on OS
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    wait_param = '-w' if platform.system().lower() == 'windows' else '-W'
    wait_value = '1000' if platform.system().lower() == 'windows' else '1' # 1000ms (Win) vs 1s (Unix)

    command = ['ping', param, '1', wait_param, wait_value, hostname]

    try:
        # Run command, suppress output
        response = subprocess.run(
            command, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        return response.returncode == 0
    except Exception as e:
        logger.error(f"Ping failed for {hostname}: {e}")
        return False
