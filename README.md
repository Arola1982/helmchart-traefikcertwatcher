# helmchart-traefikcertwatcher

The reason for this chart/operator is because when using traefik as an ingress it works perfect for http / ingress certificates however
in cases where applications need to mount the certificate into a pod such as dovecot, postfix etc in order for the application to run. Because traefik
doesnt create a secret that can be mounted this becomes a problem.

The solution here is to:

1. Periodically poll and parse the data/acme.json
2. Based on the crd object will extract certificate information for a given domain
3. Records initial hash of the certificate and if it changes it will trigger a rolling update of specific deployments / statefulsets after writing
   a secret to kubernetes so that pods can use it

## CRD Object example

```
---
apiVersion: arola.local/v1
kind: TraefikCertWatcher
metadata:
  name: example.arola.co.uk
spec:
  domain: example.arola.co.uk
  secretName: example-cert
  release: test
  managed_items:
    - name: postfix
      type: deployment
```

### Key

metadata.name - Name of the crd object for reference

spec.domain - The domain we are interest in
spec.secretName - The name of the kubernetes secret that will be created
spec.release - The release name of the managed items.

In the example above if postfix was part of a parent chart called test then the postfix deployment name would be test-postfix to internally the release and managed_item.name are merged together

managed_items - These are deployments or statefulsets that would be redeployed based on when the monitored certificate changes (With a 2 minute wait between items)

Usage:

1. Install the crd `kubectl apply -f files/crd.yaml`
2. Install the chart `helm install traefikcertwatcher .`
3. Create an object

The polling defaults to 15 minutes
