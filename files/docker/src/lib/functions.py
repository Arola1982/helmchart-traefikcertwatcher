import hashlib
import json
import datetime
import time
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client.exceptions import ApiException

traefik_namespace='kube-system'
label_selector='app.kubernetes.io/instance=traefik'

recorded_hash = ""

config.load_incluster_config()

def get_traefik_pod_info(namespace=traefik_namespace, label_selector=label_selector):
    try:
        v1 = client.CoreV1Api()
        pod_data = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector).items

        for item in pod_data:
            pod_name = item.metadata.name

        return pod_name

    except ApiException as e:
        print(f'get_traefik_pod_info : {e.reason} whilst trying to interact with the kubernetes API')

def compare_hashes(logger, domain):
    actual_hash = hashlib.sha256(get_cert_info(logger, le_domain=domain)['tls.crt'].encode()).hexdigest()

    global recorded_hash
    if actual_hash != recorded_hash:
        logger.warn(f'Certificate has changed')
        
        recorded_hash = actual_hash
        return True

def get_acme_json(logger, namespace=traefik_namespace):

    try:
        core_v1_api = client.CoreV1Api()
        exec_command = [
            '/bin/sh',
            '-c',
            'cat /data/acme.json'
        ]

        api_response = stream(
            core_v1_api.connect_get_namespaced_pod_exec,
            get_traefik_pod_info(),
            namespace,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )

        return api_response.replace('\'', '"')

    except ApiException as e:
        logger.error(f'get_acme_json : {e.reason}')

def get_cert_info(logger, le_domain):
    pod_name = get_traefik_pod_info()

    try:
        acme_json = json.loads(get_acme_json(logger))
        pod_name = get_traefik_pod_info()

        certificates = acme_json['letsencrypt']['Certificates']

        for certificate in certificates:
            domain = certificate['domain']['main']

            if domain == le_domain:
                domain_info = {}
                domain_info['tls.crt'] = certificate['certificate']
                domain_info['tls.key'] = certificate['key']

                logger.info(f"Retrieving SSL information for {le_domain} from {pod_name}")             

                return domain_info

    except json.decoder.JSONDecodeError:
        logger.error(f'get_cert_info : Unable to decode json received from {pod_name}')

def create_secret(logger, spec, namespace):
    api_version = client.CoreV1Api()
    secret_name = spec.get('secretName')
    domain = spec.get('domain')

    try:
        api_response = api_version.create_namespaced_secret(
            namespace,
            body=client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name=secret_name
                ),
                type="kubernetes.io/tls",
                data=get_cert_info(logger, le_domain=domain)
            ),
        )

        logger.info(f"Creating Secret {secret_name}")

        global recorded_hash
        recorded_hash = hashlib.sha256(get_cert_info(logger, le_domain=domain)['tls.crt'].encode()).hexdigest()
        logger.info(f'First time recording hash {recorded_hash}')

    except ApiException as e:
        if e.reason == 'Conflict':
            logger.warn(f'create_secret : Secret {secret_name} already exists, attempting an update instead')
            update_secret(logger, spec, namespace)

def update_secret(logger, spec, namespace):
    api_version = client.CoreV1Api()
    secret_name = spec.get('secretName')
    domain = spec.get('domain')

    api_response = api_version.replace_namespaced_secret(
        namespace=namespace,
        name=secret_name,
        body=client.V1Secret(
            metadata=client.V1ObjectMeta(
                name=secret_name
            ),
            type="kubernetes.io/tls",
            data=get_cert_info(logger, le_domain=domain)
        ),
    )

    logger.warn(f"Updating Secret {secret_name}")

def delete_secret(logger, spec, namespace):
    api_version = client.CoreV1Api()
    secret_name = spec.get('secretName')
    domain = spec.get('domain')

    api_response = api_version.delete_namespaced_secret(
        name = secret_name,
        namespace = namespace
    )

def rolling_update(logger, spec, namespace):
    api_version = client.AppsV1Api()
    managed_items = spec.get('managed_items')
    release = spec.get('release')

    body = {
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {
                            "lastUpdated": str(datetime.datetime.now()).replace(":", "-").replace(" ", "-")
                        }
                    }
                }
            }
        }

    for item in managed_items:
        itemName = item['name']
        itemName = f'{release}-{itemName}'
        itemType = item['type']

        wait_time = float(120)
        
        logger.warn(f'Rolling update of {itemType} | {itemName}')
        if itemType == 'deployment':
            api_response = api_version.patch_namespaced_deployment(
                name = itemName,
                namespace = namespace,
                body = body
            )

        if itemType == 'statefulset':
            api_response = api_version.patch_namespaced_stateful_set(
                name = itemName,
                namespace = namespace,
                body = body
            )

        logger.info(f'Waiting for {wait_time} seconds')
        time.sleep(wait_time)