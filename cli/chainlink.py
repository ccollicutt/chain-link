"""
This module creates a chain-link deployment in a kubernetes cluster.
"""

import os
import json
import yaml
import logging
from kubernetes import client, config
from kubernetes.client import V1SecurityContext
from .log_utils import setup_logger

setup_logger(loglevel="INFO")


class ChainLinkError(Exception):
    """
    Base class for exceptions in this module.
    """


class ObjectCreationError(ChainLinkError):
    """
    Exception raised for errors in the creation of kubernetes objects.
    """


class ChainLink:
    """
    This class creates a chain-link deployment in a kubernetes cluster.
    """

    def __init__(
        self,
        name,
        image_name,
        num_instances,
        namespace,
        sleep_time=60,
        action="deploy",
        output_directory="manifests",
    ):
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.image_name = image_name
        self.num_instances = num_instances
        self.namespace = namespace
        # gunicorn in the container listens on port 8000
        self.chain_link_target_port = 8000
        self.sleep_time = sleep_time
        self.configmap_name = f"{self.name}-services"
        self.services = self.get_service_urls()
        self.loadgerator_pod = None
        self.zipkin_service = None
        self.zipkin_deployment = None
        self.chain_link_deployments = []
        self.chain_link_services = []
        self.configmap = None
        # FIXME: bad name
        self.namespace_object = None
        self.manifests = []
        self.output_directory = output_directory

        try:
            config.load_kube_config()
        except config.config_exception.ConfigException as esc:
            raise ChainLinkError(
                "Please ensure that you have a valid kube config file."
            ) from esc

        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

        # set all the kubernetes objects
        self.set_namespace()
        self.set_config_map()
        self.set_zipkin_deployment()
        self.set_zipkin_service()
        self.set_chain_link_deployments()
        self.set_chain_link_services()
        self.set_loadgenerator_pod()

        if action == "generate":
            self.generate_manifests()

        if action == "deploy":
            self.create_namespace()
            self.create_config_map()
            self.create_zipkin_deployment()
            self.create_zipkin_service()
            self.create_chain_link_deployments()
            self.create_chain_link_services()
            self.create_loadgenerator_pod()

        if action == "validate":
            self.validate()

    def generate_manifests(self):
        """
        Generates the manifests for the chain-link deployment
        """
        for yaml_str in self.manifests:
            k8s_object = yaml.safe_load(yaml_str)
            metadata_name = k8s_object["metadata"]["name"]
            kind = str.lower(k8s_object["kind"])
            file_name = f"{metadata_name}-{kind}.yaml"

            # FIXME: I can't seem to set the namespace in objects like
            # deployment, so I'm creating it here...
            if "namespace" not in k8s_object["metadata"] and kind != "namespace":
                k8s_object["metadata"]["namespace"] = self.namespace
                yaml_str = yaml.dump(k8s_object)

            self.logger.info(
                "Writing manifest %s into %s", file_name, self.output_directory
            )

            # FIXME: do this on setup?
            config_dir = os.path.expanduser(self.output_directory)

            # FIXME: error check
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)

            try:
                with open(f"{config_dir}/{file_name}", "w", encoding="utf-8") as file:
                    file.write(yaml_str)
            except IOError as esc:
                raise ChainLinkError(f"Error writing manifest {file_name}") from esc

    def get_service_urls(self):
        """
        Returns a list of service urls for the chain-link services
        """
        return [f"{self.name}-service-{i}" for i in range(self.num_instances)]

    def create_object(
        self, obj_type, obj_name, obj_namespace, obj_body, obj_api, obj_logger
    ):
        try:
            if obj_type == "Service":
                obj_api.create_namespaced_service(
                    namespace=obj_namespace, body=obj_body
                )
            elif obj_type == "Deployment":
                obj_api.create_namespaced_deployment(
                    namespace=obj_namespace, body=obj_body
                )
            elif obj_type == "ConfigMap":
                obj_api.create_namespaced_config_map(
                    namespace=obj_namespace, body=obj_body
                )
            elif obj_type == "Pod":
                obj_api.create_namespaced_pod(namespace=obj_namespace, body=obj_body)
            elif obj_type == "Namespace":
                obj_api.create_namespace(body=obj_body)
            else:
                raise ChainLinkError(f"Unknown object type {obj_type}")

            obj_logger.info(
                f"Created {obj_type} '{obj_name}' in namespace '{obj_namespace}'"
            )
        except client.ApiException as esc:
            if esc.status == 409:
                obj_logger.warning(
                    f"{obj_type} {obj_name} already exists in namespace {obj_namespace}"
                )
            else:
                raise ObjectCreationError(
                    f"Error creating {obj_type} '{obj_name}': {esc}"
                ) from esc

    def set_namespace(self):
        """
        Creates a namespace in the kubernetes cluster
        """
        body = client.V1Namespace(
            api_version="v1",
            kind="Namespace",
            metadata=client.V1ObjectMeta(name=self.namespace),
        )

        self.namespace_object = body

        # sanitize the namespace and add it to the list of manifests
        sanitized_namespace = self.apps_api.api_client.sanitize_for_serialization(body)
        self.manifests.append(yaml.dump(sanitized_namespace, indent=2))

    def create_namespace(self):
        self.create_object(
            obj_type="Namespace",
            obj_name=self.namespace,
            obj_namespace=self.namespace,
            obj_body=self.namespace_object,
            obj_api=self.core_api,
            obj_logger=self.logger,
        )

    def set_config_map(self):
        """
        Sets a configmap in the kubernetes cluster
        """
        data = {"services.json": json.dumps(self.services)}
        configmap = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(
                namespace=self.namespace, name=self.configmap_name
            ),
            data=data,
        )

        self.configmap = configmap

        # sanitize the configmap and add it to the list of manifests
        sanitized_configmap = self.core_api.api_client.sanitize_for_serialization(
            configmap
        )
        self.manifests.append(yaml.dump(sanitized_configmap, indent=2))

    def create_config_map(self):
        self.create_object(
            obj_type="ConfigMap",
            obj_name=self.configmap_name,
            obj_namespace=self.namespace,
            obj_body=self.configmap,
            obj_api=self.core_api,
            obj_logger=self.logger,
        )

    def set_chain_link_deployments(self):
        """
        Sets the chain-link deployment in the kubernetes cluster
        """
        for i in range(self.num_instances):
            deployment_name = f"{self.name}-deployment-{i}"

            instance_num = str(i)
            labels = {
                "app": self.name,
                "instance": instance_num,
                "instance-name": f"{self.name}-{i}",
                "service-name": f"{self.name}-service-{i}",
            }

            # here we are specifying the service name which is used in the app
            container = client.V1Container(
                name=self.name,
                image=self.image_name,
                image_pull_policy="Always",
                env=[
                    client.V1EnvVar(
                        name="CHAIN_LINK_SERVICE_NAME", value=f"{self.name}-service-{i}"
                    )
                ],
                readiness_probe=client.V1Probe(
                    http_get=client.V1HTTPGetAction(
                        path="/readiness", port=8000, scheme="HTTP"
                    ),
                    initial_delay_seconds=5,
                    period_seconds=10,
                ),
            )

            # mount the configmap in the container...
            container_volume_mount = client.V1VolumeMount(
                name=self.configmap_name,
                mount_path="/etc/chain-link.conf.d",
                read_only=True,
            )

            # NOTE(curtis): we are running the container as a non-root user and
            # user is set in the dockerfile for gunicorn
            template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    security_context=client.V1PodSecurityContext(run_as_user=10001),
                    containers=[container],
                    volumes=[
                        client.V1Volume(
                            name=self.configmap_name,
                            config_map=client.V1ConfigMapVolumeSource(
                                name=self.configmap_name
                            ),
                        )
                    ],
                ),
            )
            template.spec.containers[0].volume_mounts = [container_volume_mount]
            spec = client.V1DeploymentSpec(
                replicas=1, template=template, selector={"matchLabels": labels}
            )
            # NOTE(curtis): I'm setting the api_version and kind here, it's not
            # necessary to deploy, but when I pring the deployment object it
            # isn't there unless I set it here
            deployment = client.V1Deployment(
                api_version="apps/v1",
                kind="Deployment",
                metadata=client.V1ObjectMeta(name=deployment_name),
                spec=spec,
            )

            self.chain_link_deployments.append(deployment)

            # sanitize the deployment and add it to the list of manifests
            sanitized_deployment = self.apps_api.api_client.sanitize_for_serialization(
                deployment
            )
            self.manifests.append(yaml.dump(sanitized_deployment, indent=2))

    def create_chain_link_deployments(self):
        """
        Creates a chain-link deployment in the kubernetes cluster
        """
        for deployment in self.chain_link_deployments:
            deployment_name = deployment.metadata.name
            self.create_object(
                obj_type="Deployment",
                obj_name=deployment_name,
                obj_namespace=self.namespace,
                obj_body=deployment,
                obj_api=self.apps_api,
                obj_logger=self.logger,
            )

    def set_chain_link_services(self):
        """
        Creates a chain-link service in the kubernetes cluster
        """
        for i in range(self.num_instances):
            instance_num = str(i)
            service_name = f"{self.name}-service-{i}"
            labels = {
                "app": self.name,
                "instance": instance_num,
                "instance-name": f"{self.name}-{i}",
                "service-name": service_name,
            }

            service_port = client.V1ServicePort(
                port=80, target_port=self.chain_link_target_port
            )
            service_spec = client.V1ServiceSpec(
                ports=[service_port], selector=labels, type="ClusterIP"
            )

            service_metadata = client.V1ObjectMeta(name=service_name, labels=labels)
            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=service_metadata,
                spec=service_spec,
            )

            self.chain_link_services.append(service)

            # sanitize the service and add it to the list of manifests
            sanitized_service = self.core_api.api_client.sanitize_for_serialization(
                service
            )

            self.manifests.append(yaml.dump(sanitized_service, indent=2))

    def create_chain_link_services(self):
        """
        Creates a chain-link service in the kubernetes cluster
        """
        for service in self.chain_link_services:
            service_name = service.metadata.name
            self.create_object(
                obj_type="Service",
                obj_name=service_name,
                obj_namespace=self.namespace,
                obj_body=service,
                obj_api=self.core_api,
                obj_logger=self.logger,
            )

    def set_zipkin_deployment(self):
        """
        Creates a zipkin deployment in the kubernetes cluster
        """
        deployment_name = "zipkin-deployment"

        labels = {"app": "chain-link", "instance": "zipkin"}

        container = client.V1Container(
            name="zipkin",
            image="openzipkin/zipkin",
            image_pull_policy="Always",
            ports=[client.V1ContainerPort(container_port=9411)],
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=labels),
            spec=client.V1PodSpec(containers=[container]),
        )
        spec = client.V1DeploymentSpec(
            replicas=1, template=template, selector={"matchLabels": labels}
        )
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=deployment_name),
            spec=spec,
        )

        self.zipkin_deployment = deployment

        # sanitize the deployment and add it to the list of manifests
        sanitized_deployment = self.apps_api.api_client.sanitize_for_serialization(
            deployment
        )
        self.manifests.append(yaml.dump(sanitized_deployment, indent=2))

    def create_zipkin_deployment(self):
        """
        Creates a zipkin deployment in the kubernetes cluster
        """
        deployment_name = self.zipkin_deployment.metadata.name
        self.create_object(
            obj_type="Deployment",
            obj_name=deployment_name,
            obj_namespace=self.namespace,
            obj_body=self.zipkin_deployment,
            obj_api=self.apps_api,
            obj_logger=self.logger,
        )

    def set_zipkin_service(self):
        """
        Creates a zipkin service in the kubernetes cluster
        """
        service_name = "zipkin-service"
        labels = {"app": self.name, "instance": "zipkin"}

        service_port = client.V1ServicePort(port=80, target_port=9411)
        service_spec = client.V1ServiceSpec(
            ports=[service_port], selector=labels, type="ClusterIP"
        )

        service_metadata = client.V1ObjectMeta(name=service_name, labels=labels)
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=service_metadata,
            spec=service_spec,
        )

        self.zipkin_service = service

        # sanitize the service and add it to the list of manifests
        sanitized_service = self.core_api.api_client.sanitize_for_serialization(service)
        self.manifests.append(yaml.dump(sanitized_service, indent=2))

    def create_zipkin_service(self):
        """
        Creates a zipkin service in the kubernetes cluster
        """
        service_name = self.zipkin_service.metadata.name
        self.create_object(
            obj_type="Service",
            obj_name=service_name,
            obj_namespace=self.namespace,
            obj_body=self.zipkin_service,
            obj_api=self.core_api,
            obj_logger=self.logger,
        )

    def set_loadgenerator_pod(self):
        """
        Sets the loadgenerator pod
        """
        pod_name = "loadgenerator"
        # Create labels for the pod
        labels = {"app": "chain-link", "service": "loadgenerator"}

        # Define the container spec
        st = self.sleep_time
        container = client.V1Container(
            name="busybox",
            image="busybox",
            command=[
                "/bin/sh",
                "-c",
                f"while sleep {st}; do wget -qO- chain-link-service-0; done",
            ],
            security_context=V1SecurityContext(
                run_as_user=65534
            ),  # Use user 'nobody' (usually has UID 65534)
        )

        pod_spec = client.V1PodSpec(restart_policy="Never", containers=[container])
        pod_metadata = client.V1ObjectMeta(name=pod_name, labels=labels)
        pod = client.V1Pod(
            api_version="v1", kind="Pod", metadata=pod_metadata, spec=pod_spec
        )

        self.loadgerator_pod = pod

        # sanitize the pod and add it to the list of manifests
        sanitized_pod = self.core_api.api_client.sanitize_for_serialization(pod)
        self.manifests.append(yaml.dump(sanitized_pod, indent=2))

    def create_loadgenerator_pod(self):
        """
        Creates the loadgenerator pod
        """
        pod_name = self.loadgerator_pod.metadata.name
        self.create_object(
            obj_type="Pod",
            obj_name=pod_name,
            obj_namespace=self.namespace,
            obj_body=self.loadgerator_pod,
            obj_api=self.core_api,
            obj_logger=self.logger,
        )

    def validate(self):
        """
        Checks if all the deployments and pods are running.
        """
        deployments_ready = True
        pods_ready = True

        self.logger.info("Validating deployments...")

        # Check the status of Deployments
        for i in range(self.num_instances):
            deployment_name = f"{self.name}-deployment-{i}"
            try:
                deployment = self.apps_api.read_namespaced_deployment_status(
                    deployment_name, self.namespace
                )
                if deployment.status.replicas != deployment.status.ready_replicas:
                    deployments_ready = False
                    self.logger.warning("Deployment '%s' is not ready", deployment_name)
            except client.ApiException as esc:
                self.logger.error(
                    "Error reading Deployment status for '%s': %s",
                    deployment_name,
                    esc,
                )
                deployments_ready = False

        if deployments_ready:
            self.logger.info("Deployments ready")
        else:
            self.logger.error("Deployments not ready")
        self.logger.info("Validating pods...")

        # Check the status of the loadgenerator Pod
        pod_name = "loadgenerator"
        try:
            pod = self.core_api.read_namespaced_pod_status(pod_name, self.namespace)
            if pod.status.phase != "Running":
                pods_ready = False
                self.logger.warning("Pod '%s' is not running", pod_name)
        except client.ApiException as esc:
            self.logger.error("Error reading Pod status for '%s': %s", pod_name, esc)
            pods_ready = False

        if not pods_ready:
            self.logger.error("Pods not ready")
        else:
            self.logger.info("Pods ready")

        if deployments_ready and pods_ready:
            self.logger.info("All objects ready")
