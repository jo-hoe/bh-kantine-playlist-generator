
include help.mk

# get root dir
ROOT_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PYTHON_DIR := ${ROOT_DIR}.venv/Scripts/
IMAGE_NAME := "bh-kantine-playlist-generator"

.DEFAULT_GOAL := start-docker

.PHONY: init
init: venv update ## init setup of project after checkout

.PHONY: venv
venv:
	@python -m venv ${ROOT_DIR}.venv

.PHONY: pull
pull:
	@git -C ${ROOT_DIR} pull

.PHONY: update
update: pull ## pulls git repo and installs all dependencies
	${PYTHON_DIR}pip install -r ${ROOT_DIR}requirements.txt

.PHONY: save-dependencies
save-dependencies: ## save current dependencies
	"${PYTHON_DIR}pip" list --not-required --format=freeze | grep -v "pip" > "${ROOT_DIR}requirements.txt"

.PHONY: test
test: ## run all tests
	${PYTHON_DIR}pytest $(ROOT_DIR)test/

.PHONY: start-docker
start-docker:
	@docker compose -f ${ROOT_DIR}compose.yaml up --build 

