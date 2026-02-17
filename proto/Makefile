PROTO_DIR := .
PROTO_FILES := $(wildcard market/v1/*.proto) $(wildcard probe/v1/*.proto)
GEN_GO := gen/go
GEN_PYTHON := gen/python
GEN_CPP := gen/cpp

.PHONY: all go python cpp clean

all: go python cpp

go:
	@mkdir -p $(GEN_GO)
	protoc \
		--proto_path=$(PROTO_DIR) \
		--go_out=$(GEN_GO) --go_opt=paths=source_relative \
		--go-grpc_out=$(GEN_GO) --go-grpc_opt=paths=source_relative \
		$(PROTO_FILES)

python:
	@mkdir -p $(GEN_PYTHON)
	python -m grpc_tools.protoc \
		--proto_path=$(PROTO_DIR) \
		--python_out=$(GEN_PYTHON) \
		--pyi_out=$(GEN_PYTHON) \
		--grpc_python_out=$(GEN_PYTHON) \
		$(PROTO_FILES)

cpp:
	@mkdir -p $(GEN_CPP)
	protoc \
		--proto_path=$(PROTO_DIR) \
		--cpp_out=$(GEN_CPP) \
		--grpc_out=$(GEN_CPP) \
		--plugin=protoc-gen-grpc=`which grpc_cpp_plugin` \
		$(PROTO_FILES)

clean:
	rm -rf $(GEN_GO) $(GEN_PYTHON) $(GEN_CPP)
