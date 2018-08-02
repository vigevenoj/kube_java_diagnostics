#!/usr/bin/env python3
import argparse
import datetime
import logging
import sys
from kubernetes import client, config
from kubernetes.stream import stream


class KubeJavaDiagnostics():
    """
    Collect diagnostic information from a containerized Java application
    running in a kubernetes cluster. Tool is a wrapper allowing us to take
    thread dumps and collect a histogram of memory usage without having to
    directly use kubectl to look up process id and provide other details.
    """
    def __init__(self, args):
        """
        Parse the provided args dict to load our options, load the
        kubernetes configuration, and configure logging.
        """
        config.load_kube_config()
        self._namespace = args.namespace
        self._container = args.container
        self._main_class = args.main
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(formatter)

    def get_jive_pid(self, pod_name):
        """
        Return the process ID of the jive application process inside the
        container.
        Relies on the main class of the java process including the string
        defined in the main_class variable above
        """
        exec_command = ['jcmd']
        v1 = client.CoreV1Api()
        resp = stream(v1.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace=self._namespace,
                      command=exec_command,
                      container=self._container,
                      stderr=True,
                      stdin=False,
                      stdout=True,
                      tty=False)
        for line in resp.splitlines():
            if self._main_class in line:
                pid = line.split(' ')[0]
                if pid.isnumeric():
                    return pid
        self._logger.error("No PID for jive bootstrap process found")
        pass

    def dump_threads(self, pod_name, pid):
        """
        Dump the threads in the application running in the named pod.
        """
        # construct our command
        exec_command = ["jcmd", pid, "Thread.print"]
        # execute it
        v1 = client.CoreV1Api()
        resp = stream(v1.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace=self._namespace,
                      command=exec_command,
                      container=self._container,
                      stderr=True,
                      stdin=False,
                      stdout=True,
                      tty=False)
        return resp

    def get_histogram(self, pod_name, pid):
        """
        Return a class histogram from the specified pid in the specified pod
        """
        exec_command = ["jcmd", pid, "GC.class_histogram"]
        v1 = client.CoreV1Api()
        resp = stream(v1.connect_get_namespaced_pod_exec,
                      pod_name,
                      namespace=self._namespace,
                      command=exec_command,
                      container=self._container,
                      stderr=True,
                      stdin=False,
                      stdout=True,
                      tty=False)
        return resp


def save_thread_dump(namespace, pod_name, thread_dump):
    """
    Helper to save thread dump to file
    """
    # TODO: save as file
    timestamp = '{0:%Y%m%d-%H%M}'.format(datetime.datetime.now())
    filename = "{0}_{1}_{2}_threaddump.out".format(namespace,
                                                   pod_name,
                                                   timestamp)
    with open(filename, 'w') as output:
        output.write(thread_dump)
        print("Saved thread dump as {0}".format(filename))


def save_histogram(namespace, pod_name, histogram):
    """
    Helper to save class histogram to a file
    """
    # TODO: save as file
    timestamp = '{0:%Y%m%d-%H%M}'.format(datetime.datetime.now())
    filename = "{0}_{1}_{2}_histogram.txt".format(namespace,
                                                  pod_name,
                                                  timestamp)
    with open(filename, 'w') as output:
        output.write(histogram)
        print("Saved histogram as {0}".format(filename))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="""A tool to collect diagnostics from java applications
        that are running in a kubernetes cluster. Assumes that any pods found
        will contain a JVM running the specified main class, and will attempt
        to take and save thread dumps and a histogram of the heap usage from
        the application to the local filesystem.
        """)
    parser.add_argument("namespace",
                        help="kubernetes namespace for application")
    # The webapp component has this label and we filter by it
    parser.add_argument("--label",
                        help="filter pods in namespace by this label",
                        default="jcx.inst.component=webapp")
    parser.add_argument("--pod",
                        help="name of pod in which take thread dumps")
    parser.add_argument("--container",
                        help="name of the container in the pod",
                        default="webapp")
    # The main class of the java process has this string in it
    parser.add_argument("--main",
                        help="name of the main class in the JVM",
                        default="Bootstrap")
    args = parser.parse_args()

    snapper = KubeJavaDiagnostics(args)
    if args.pod:
        # Get diagnostics from only a single pod
        pid = snapper.get_jive_pid(args.pod)

        threads = snapper.dump_threads(args.pod, pid)
        histogram = snapper.get_histogram(args.pod, pid)

        save_thread_dump(args.namespace, args.pod, threads)
        save_histogram(args.namespace, args.pod, histogram)
    else:
        # Get diagnostics from all pods in the namespace
        v1 = client.CoreV1Api()
        pod_list = v1.list_namespaced_pod(args.namespace,
                                          label_selector=args.label)
        for pod in pod_list.items:
            pid = snapper.get_jive_pid(pod.metadata.name)

            threads = snapper.dump_threads(pod.metadata.name, pid)
            histogram = snapper.get_histogram(pod.metadata.name, pid)

            save_thread_dump(args.namespace, pod.metadata.name, threads)
            save_histogram(args.namespace, pod.metadata.name, histogram)
