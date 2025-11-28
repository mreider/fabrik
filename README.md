# Fabrik II Demo

This demo showcases the difference between Dynatrace OneAgent instrumentation and OpenTelemetry instrumentation.

## Structure

*   `apps/`: Source code for Frontend, Orders, Fulfillment, and Load Generator services.
*   `k8s/`: Kubernetes manifests.
*   `.github/workflows/`: CI/CD workflow to build and push images.

## Prerequisites

*   Google Cloud SDK (`gcloud`)
*   `kubectl`
*   Dynatrace Environment (URL and API Token)

## Setup

1.  **Create GKE Cluster**:
    ```bash
    ./create-cluster.sh
    ```

2.  **Push to GitHub**:
    Push this repository to GitHub to trigger the image build workflow.
    ```bash
    git add .
    git commit -m "Initial commit"
    git push
    ```

3.  **Deploy**:
    Set your Dynatrace API Token:
    ```bash
    export DT_API_TOKEN=dt0c01...
    ```
    Run the deployment script:
    ```bash
    ./deploy.sh
    ```

## Architecture

*   **Namespace `fabrik-oa`**: OneAgent injected automatically via Dynatrace Operator.
*   **Namespace `fabrik-ot`**: OpenTelemetry Java Agent manually added, exporting directly to Dynatrace OTLP endpoint.
