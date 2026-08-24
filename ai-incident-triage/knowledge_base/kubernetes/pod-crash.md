# Kubernetes Pod Lifecycle Issues

## CrashLoopBackOff

A `CrashLoopBackOff` indicates that a pod is starting, crashing, and then starting again in a loop.

**Common Causes:**
- Application misconfiguration (missing environment variables, invalid config files).
- The application is trying to allocate more memory than the limit, causing OOMKilled before crashing.
- Database connection failures on startup.
- Uncaught exceptions during initialization.

**Resolution Steps:**
1. Check the pod logs for the previous crashed container: `kubectl logs <pod-name> --previous`
2. Check the events for the pod: `kubectl describe pod <pod-name>`
3. Verify if it's an OOMKilled by checking the container state in the pod description.

## ImagePullBackOff

An `ImagePullBackOff` indicates that the container runtime was unable to pull the container image.

**Common Causes:**
- The image tag does not exist in the registry.
- Network issues preventing the node from reaching the container registry.
- Authentication issues (missing or invalid imagePullSecrets).

**Resolution Steps:**
1. Check the exact error message in the events: `kubectl describe pod <pod-name>`
2. Verify the image name and tag are correct.
3. Verify the registry credentials if it's a private registry.
