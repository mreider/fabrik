#!/bin/bash
set -e

CLUSTER_NAME="fabrik-demo"
ZONE="us-central1-a"
PROJECT_ID=$(gcloud config get-value project)

echo "Creating GKE cluster $CLUSTER_NAME in $ZONE..."

gcloud container clusters create "$CLUSTER_NAME" \
  --zone "$ZONE" \
  --machine-type "e2-standard-4" \
  --num-nodes "1" \
  --enable-autoscaling --min-nodes "1" --max-nodes "3" \
  --disk-size "30" \
  --disk-type "pd-standard" \
  --scopes "https://www.googleapis.com/auth/cloud-platform" \
  --project "$PROJECT_ID"

echo "Getting credentials..."
gcloud container clusters get-credentials "$CLUSTER_NAME" --zone "$ZONE" --project "$PROJECT_ID"

echo "Cluster created and credentials configured."
