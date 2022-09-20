from sys import stderr, stdin
from lib.functions import create_secret, delete_secret, compare_hashes, update_secret, rolling_update
import tty
import kopf
import asyncio
import os

timer_poll_interval = float(os.getenv('POLL_INTERVAL', 30))

@kopf.on.create('traefikcertwatchers')
def create_fn(logger, spec, namespace, **kwargs):
    domain = spec.get('domain')

    logger.info(f"Creating secret for {domain}")
    create_secret(logger, spec, namespace)

@kopf.on.delete('traefikcertwatchers')
def delete_fn(logger, spec, namespace, **kwargs):
    domain = spec.get('domain')

    logger.info(f"Deleting secret for {domain}")
    delete_secret(logger, spec, namespace)

@kopf.timer('traefikcertwatchers', interval=timer_poll_interval)
def timer_fn(logger, spec, namespace,  **kwargs):
    domain = spec.get('domain')

    if compare_hashes(logger, domain):
        update_secret(logger, spec, namespace)
        rolling_update(logger, spec, namespace)
        
    logger.info(f'Next check in {timer_poll_interval} seconds')