include help.mk

# get root dir
ROOT_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
IMAGE_NAME := "bh-playlist-generator"
IMAGE_VERSION := "latest"

.DEFAULT_GOAL := help

.PHONY: venv
venv:
	@python -m venv ${ROOT_DIR}.venv

.PHONY: pull
pull:
	@git -C ${ROOT_DIR} pull

.PHONY: update
update: pull ## pulls git repo and installs all dependencies
	${PYTHON_DIR}pip install -r ${ROOT_DIR}requirements.txt

.PHONY: build
build: ## build docker image
	@docker build -f ${ROOT_DIR}Dockerfile . -t ${IMAGE_NAME}

.PHONY: save-dependencies
save-dependencies: ## save current dependencies
	"${PYTHON_DIR}pip" list --not-required --format=freeze | grep -v "pip" > "${ROOT_DIR}requirements.txt"

.PHONY: start-cluster
start-cluster: ## starts k3d cluster and registry (injects host cache volume)
	@python ${ROOT_DIR}k3d/deploy-k3d.py --create-cluster

.PHONY: start-k3d
start-k3d: start-cluster push-k3d ## start k3d cluster and deploy chart
	@python ${ROOT_DIR}k3d/deploy-k3d.py --image-name ${IMAGE_NAME} --image-version ${IMAGE_VERSION}

.PHONY: stop-k3d
stop-k3d: ## stop K3d cluster
	@k3d cluster delete --config ${ROOT_DIR}k3d/clusterconfig.yaml

.PHONY: restart-k3d
restart-k3d: stop-k3d start-k3d ## restart K3d cluster

.PHONY: push-k3d
push-k3d: build ## build and push docker image to local registry
	@docker tag ${IMAGE_NAME} localhost:5001/${IMAGE_NAME}:${IMAGE_VERSION}
	@docker push localhost:5001/${IMAGE_NAME}:${IMAGE_VERSION}

.PHONY: test-chart
test-chart: ## run helm template and lint on chart
	@helm template ${IMAGE_NAME} ${ROOT_DIR}charts/${IMAGE_NAME}
	@helm lint ${ROOT_DIR}charts/${IMAGE_NAME}

.PHONY: status-k3d
status-k3d: ## show status of all resources
	@echo "=== Pods ==="
	@kubectl get pods -l app.kubernetes.io/name=bh-playlist-generator
	@echo "=== CronJobs ==="
	@kubectl get cronjobs -l app.kubernetes.io/name=bh-playlist-generator
	@echo "=== PersistentVolumes ==="
	@kubectl get pv
	@echo "=== PersistentVolumeClaims ==="
	@kubectl get pvc
	@echo "=== ConfigMaps ==="
	@kubectl get configmap -l app.kubernetes.io/name=bh-playlist-generator
	@echo "=== Secrets ==="
	@kubectl get secret -l app.kubernetes.io/name=bh-playlist-generator


.PHONY: generate-helm-docs
generate-helm-docs: ## re-generates helm docs using docker
	@docker run --rm --volume "$(ROOT_DIR)charts:/helm-docs" jnorwood/helm-docs:latest
