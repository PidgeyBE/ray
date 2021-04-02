import os
import logging
import kubernetes
from kubernetes.config.config_exception import ConfigException
from kubernetes.client.rest import ApiException
from tenacity import retry, wait_fixed, retry_if_exception_type

_configured = False
_core_api = None
_auth_api = None
_extensions_beta_api = None

logger = logging.getLogger(__name__)
# Has to be an integer (for requests lib compat)!
TIMEOUT = int(os.environ.get("RAY_K8S_TIMEOUT", 10))

class CustomRetryError(Exception):
    pass

# For kubernetes==10.0.1 kubernetes-asyncio==10.0.0
class K8Safe:
    def __init__(self, object):
        self.object = object

    def __getattr__(self, name):
        attribute = getattr(self.object, name)
        if not callable(attribute):
            return attribute
        else:
            @retry(
                wait=wait_fixed(TIMEOUT),
                reraise=True,
                retry=retry_if_exception_type(CustomRetryError)
            )
            def retry_safe(*args, **kwargs):
                """Infinite retry and lower timeout of k8s API calls"""
                try:
                    return attribute(
                        *args,
                        **kwargs,
                        _request_timeout=TIMEOUT,
                    )
                except Exception as e:
                    logger.error(
                        f"K8S API call `{name}` failed: {str(e)}!"
                    )
                    if isinstance(e, ApiException):
                        logger.error(f"Exception was valid k8s exception (e.g. 404)")
                        raise e
                    else:
                        logger.error(f"Retrying...")
                        raise CustomRetryError()

            return retry_safe


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
        _auth_api = K8Safe(kubernetes.client.RbacAuthorizationV1Api())

    return _auth_api


def extensions_beta_api():
    global _extensions_beta_api
    if _extensions_beta_api is None:
        _load_config()
        _extensions_beta_api = K8Safe(kubernetes.client.ExtensionsV1beta1Api())

    return _extensions_beta_api


log_prefix = "KubernetesNodeProvider: "
