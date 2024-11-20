include ./Makefile.vars
#-include ./.env

.PHONY: all push build run setup clean

.DEFAULT_GOAL := help 
help: # Show this help
	@grep -E -h '\s#\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?# "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

#PYTHON-ENV-SPECIFIC
VENV_DIR = venv
PYTHON = python3
PIP = $(VENV_DIR)/bin/pip

IMAGE_URL = $(IMAGE_REGISTRY)$(if $(IMAGE_REGISTRY),/)$(IMAGE_PATH)

#TAG_COMMIT := $(shell git rev-list --abbrev-commit --tags --max-count=1)
# `2>/dev/null` suppress errors and `|| true` suppress the error codes.
# TAG := $(shell git describe --abbrev=0 --tags ${TAG_COMMIT} 2>/dev/null || true)

TAG := $(shell git describe --exact-match --abbrev=0 2>/dev/null)

# with stripped version prefix
#VERSION := $(TAG:v%=%)
# pure tag
VERSION := $(TAG)

#https://dev.to/eugenebabichenko/generating-pretty-version-strings-including-nightly-with-git-and-makefiles-48p3
## get the latest commit hash in the short form
#COMMIT := $(shell git rev-parse --short HEAD)
## get the latest commit date in the form of YYYYmmdd
#DATE := $(shell git log -1 --format=%cd --date=format:"%Y%m%d")
## check if the version string is empty
##ifeq ($(VERSION),)
##VERSION := $(COMMIT)-$(DATE)
##endif

# print variable
print-%: ; @echo $*=$($*) # Print value of `%` variable

# check current environment against list of provided (allowed) environments
check-env = \
    $(if $(filter $(ENV),$(1)), \
        @echo "Environment is $(ENV). Proceeding...", \
        $(error This target can only be executed in one of the following environments: $(1)))


build: # Build docker image
	docker build -t ${IMAGE_URL}:latest -f Dockerfile .
ifneq ($(VERSION),)
	docker tag ${IMAGE_URL}:latest ${IMAGE_URL}:${VERSION} -f Dockerfile .
endif


push: build # Push docker image to registry
	$(call check-env,prod)
ifneq ($(VERSION),)
	docker push ${IMAGE_URL}:latest ${IMAGE_URL}:${VERSION}
else
	docker push ${IMAGE_URL}:latest
endif


run: build # Run with docker
	$(call check-env,local)
	docker compose up


run-dockerless: setup # Run without docker
	$(call check-env,local)
	. venv/bin/activate && (\
		python3 -c "import sys; print(f'Python prefix path: {sys.prefix}')"; \
      	pip3 -V ; \
		cd websupportsk_ddns && python3 websupportsk_ddns.py $(ARGS) \
    )


setup: $(VENV_DIR) # Setup local environment


$(VENV_DIR):
	$(PYTHON) -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt


clean: # Clean local environment
	rm -rf $(VENV_DIR)


all: build push # Build and push to registry

