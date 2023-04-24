"""
This app forwards a request to the next service in the chain
"""

import os
import logging
import json
import random
import requests
import time
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from flask import Flask, request, jsonify, make_response


#
# OpenTelemetry and Zipkin
#

# Configure the TracerProvider and SpanExporter
# service_name is set in the cli.py script as a env var
service_name = os.environ.get("CHAIN_LINK_SERVICE_NAME", "unknown")
trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": service_name}))
)

# create a ZipkinSpanExporter - this is specific to Zipkin deployed into
# Kubernetes with the cli.py script
# NOTE(curtis): this is expecting a service called zipkin-service-0 listening on
# port 80!
zipkin_exporter = ZipkinExporter(
    endpoint="http://zipkin-service/api/v2/spans",
)

# Create a BatchSpanProcessor and add the exporter to it
span_processor = BatchSpanProcessor(zipkin_exporter)

# add to the tracer
trace.get_tracer_provider().add_span_processor(span_processor)

#
# Flask
#

# Instrument the Flask app and Requests library
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

#
# Logging
#

logging.basicConfig(level=logging.INFO)
app.logger.info("service_name %s", service_name)


# the services.json will be mounted from a configmap
def get_service_urls():
    """
    Get the list of services from the configmap which is mounted into the pod
    """
    with open(
        "/etc/chain-link.conf.d/services.json", encoding="utf-8"
    ) as services_file:
        services_json = services_file.read()
    return json.loads(services_json)


services = get_service_urls()
app.logger.info("new services: %s", services)


def is_valid_service(svc_name):
    """
    Check if the service_name is in the services list
    """
    return svc_name in services


#
# Routes
#


@app.route("/", methods=["GET"])
def process_request():
    """
    Process the request and forward it to the next service in the chain
    """

    # one of the nodes should take longer to respond, so we are going to randomly
    # sleep for 2 seconds on one of the nodes (well, this isn't perfect but you
    # get the idea)
    random_number = random.random()
    app.logger.info(f"Node's random_number: {random_number}")
    if random_number < 1 / len(services):
        sleep_duration = 2  # Sleep for 2 seconds
        app.logger.info("This node is sleeping for %s seconds", sleep_duration)
        time.sleep(sleep_duration)

    current_service = request.headers.get("X-Current-Service", service_name)

    # check if the current service is valid and then set the index in the chain
    # to the current service
    if current_service and not is_valid_service(current_service):
        return make_response(jsonify({"message": "Invalid service"}), 400)
    elif current_service:
        app.logger.info("current_service: %s", current_service)
        index = services.index(current_service)
    else:
        index = 0

    # if the current service is not the last service in the chain, then forward
    # the request to the next service in the chain
    if index + 1 < len(services):
        next_service = services[index + 1]
        app.logger.info("next_service: %s", next_service)
        headers = {"X-Current-Service": next_service}
        response = requests.get(
            f"http://{next_service}/forward", headers=headers, timeout=3
        )
        return response.text, response.status_code
    else:
        return (
            jsonify(
                {"message": f"You have reached the final chain link {current_service}"}
            ),
            200,
        )


# I just want a route named /forward :)
@app.route("/forward", methods=["GET"])
def forward_request():
    """
    Forward the request to the next service in the chain
    """
    return process_request()


@app.route("/readiness", methods=["GET"])
def readiness():
    """
    Readiness probe
    """
    return make_response(jsonify({"message": "ok"}), 200)


#
# Main
#

# if running out of gunicorn, use the gunicorn logger
# https://trstringer.com/logging-flask-gunicorn-the-manageable-way/
if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_RUN_PORT", "8080"))
    app.logging.info("port: %s", port)
    app.run(host="0.0.0.0", port=port)
