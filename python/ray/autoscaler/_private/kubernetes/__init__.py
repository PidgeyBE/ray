import logging
import kubernetes
from kubernetes.config.config_exception import ConfigException
from tenacity import retry, wait_fixed

_configured = False
_core_api = None
_auth_api = None
_extensions_beta_api = None

logger = logging.getLogger(__name__)

class K8Safe:
    def __init__(self, object):
        self.object = object

    def __getattr__(self, name):
        attribute = getattr(self.object, name)
        if callable(attribute):

            @retry(wait=wait_fixed(10), reraise=True)
            def retry_safe(*args, **kwargs):
                """Infinite retry and lower timeout of k8s API calls"""
                try:
                    result = attribute(*args, **kwargs, _request_timeout=5)
                    return result
                except Exception as e:
                    logger.error(f"K8S API call failed: {str(e)}! Retrying...")
                    raise e

            return retry_safe
        else:
            return attribute


def _load_config():
    global _configured
    if _configured:
        return
    try:
        kubernetes.config.load_incluster_config()
    except ConfigException:
        kubernetes.config.load_kube_config()
    _configured = True


def core_api():
    global _core_api
    if _core_api is None:
        _load_config()
        _core_api = K8Safe(kubernetes.client.CoreV1Api())

    return _core_api


def auth_api():
    global _auth_api
    if _auth_api is None:
        _load_config()
        _auth_api = kubernetes.client.RbacAuthorizationV1Api()

    return _auth_api


def extensions_beta_api():
    global _extensions_beta_api
    if _extensions_beta_api is None:
        _load_config()
        _extensions_beta_api = K8Safe(kubernetes.client.ExtensionsV1beta1Api())

    return _extensions_beta_api


log_prefix = "KubernetesNodeProvider: "
