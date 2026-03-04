# Stage 1: OpenAPI Generator
FROM openapitools/openapi-generator-cli:latest AS generator
WORKDIR /gen
COPY openapi/openapi.yaml ./

RUN bash /usr/local/bin/docker-entrypoint.sh generate \
    -g python-fastapi \
    -i openapi.yaml \
    -o /out \
    -p packageName=openapi_server \
    -p sourceFolder=src \
    -p fastapiImplementationPackage=impl \
    --global-property apis,models \
    --skip-validate-spec

# Stage 2: datamodel-codegen (Pydantic v2 модели)
FROM python:3.11-slim AS models
WORKDIR /gen
COPY openapi/openapi.yaml ./
COPY fix_generated.py ./

RUN pip install --no-cache-dir "datamodel-code-generator>=0.25.0" && \
    mkdir -p /out/schemas && \
    datamodel-codegen \
        --input openapi.yaml \
        --input-file-type openapi \
        --output /out/schemas/generated.py \
        --target-python-version 3.10 \
        --field-constraints \
        --use-standard-collections \
        --base-class pydantic.BaseModel && \
    python3 fix_generated.py /out/schemas/generated.py

# Stage 3: финальный образ
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --from=generator /out/src/openapi_server ./src/openapi_server
RUN rm -rf src/openapi_server/models

COPY --from=models /out/schemas/generated.py ./src/schemas/
RUN python3 fix_api_imports.py

COPY impl/ ./src/openapi_server/impl/
COPY impl/security_api.py ./src/openapi_server/security_api.py
RUN rm -rf ./src/openapi_server/models 2>/dev/null || true

RUN test -d src/openapi_server/apis || (echo "openapi_server/apis not found" && exit 1)

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

COPY docker_entrypoint.py /app/docker_entrypoint.py
CMD ["python", "/app/docker_entrypoint.py"]
