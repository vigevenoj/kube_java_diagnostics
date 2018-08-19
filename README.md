# kube_java_diagnostics
Wrapper around the Python Kubernetes client to get some diagnostic information from JVMs running in pods, specifically thread dumps and class histograms.

# Prerequisites
1. A working kubectl configuration
1. python3

# Installation
1. Clone the repository
1. `pip install -r requirements.txt` (in a virtualenv, probably :) )

# Usage
Available options:
* `--namespace` (required): what namespace the pods are in
* `--label`: If the Java application is in pods that have a label, use this to restrict to which pods the script connects
* `--pod`: If you want to connect to only a single pod, specify it here
* `--container`: If the pod contains multiple containers, specify the name of the container running the Java application
* `--main`: Specify the main class running in the JVM

The script will collect thread dumps and a class histogram from each JVM it connects to, and save them to files named based on the namespace and pod name, like `namespace_podname_yyyymmdd-HHMM_threaddump.out` and `namespace_podname_yyyymmdd-HHMM_histogram.txt`
