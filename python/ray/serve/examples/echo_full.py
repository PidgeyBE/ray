import time

import requests

import ray
import ray.serve as serve

# initialize ray serve system.
ray.init(num_cpus=10)
client = serve.start()


# a backend can be a function or class.
# it can be made to be invoked from web as well as python.
def echo_v1(flask_request):
    response = flask_request.args.get("response", "web")
    return response


client.create_backend("echo:v1", echo_v1)

# An endpoint is associated with an HTTP path and traffic to the endpoint
# will be serviced by the echo:v1 backend.
client.create_endpoint("my_endpoint", backend="echo:v1", route="/echo")

print(requests.get("http://127.0.0.1:8000/echo", timeout=0.5).text)
# The service will be reachable from http

print(ray.get(client.get_handle("my_endpoint").remote(response="hello")))

# as well as within the ray system.


# We can also add a new backend and split the traffic.
def echo_v2(flask_request):
    # magic, only from web.
    return "something new"


client.create_backend("echo:v2", echo_v2)

# The two backend will now split the traffic 50%-50%.
client.set_traffic("my_endpoint", {"echo:v1": 0.5, "echo:v2": 0.5})

# Observe requests are now split between two backends.
for _ in range(10):
    print(requests.get("http://127.0.0.1:8000/echo").text)
    time.sleep(0.2)

# You can also change number of replicas for each backend independently.
client.update_backend_config("echo:v1", {"num_replicas": 2})
client.update_backend_config("echo:v2", {"num_replicas": 2})
