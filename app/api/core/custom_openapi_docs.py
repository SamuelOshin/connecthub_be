from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from app.api.core.schemas.error_schema import ErrorResponseModel
from app.api.core.schemas.success_schema import SuccessResponseModel

SKIP_PATHS = {"/", "/health", "/docs", "/redoc"}

ERROR_MAP = {
    "get": ["400", "401", "422", "404", "500"],
    "post": ["400", "401", "403", "422", "500"],
    "patch": ["400", "401", "404", "422", "500"],
    "put": ["400", "401", "404", "422", "500"],
    "delete": ["400", "401", "404", "500"],
}

DEFAULT_SUCCESS_BY_METHOD = {
    "get": 200,
    "post": 201,
    "patch": 200,
    "put": 200,
    "delete": 204,
}


def custom_openapi(app: FastAPI):
    """
    Generate a customized OpenAPI schema for the FastAPI application.

    This function dynamically injects standardized success and error responses
    into all routes, while preserving any examples defined in route decorators.

    Success responses:
        - Use SuccessResponseModel as the schema.
        - Can be customized per endpoint via the `_custom_success` attribute.
        - Preserves examples defined in the route's decorator.

    Error responses:
        - Use ErrorResponseModel as the schema.
        - Endpoint-specific errors can be defined via `_custom_errors`.
        - Defaults are provided per HTTP method if `_custom_errors` is not set.

    Paths in `SKIP_PATHS` are excluded from injection.

    Args:
        app (FastAPI): The FastAPI application instance.

    Returns:
        dict: The customized OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in SKIP_PATHS:
            continue

        endpoint = getattr(route, "endpoint", None)
        custom_errors = getattr(endpoint, "_custom_errors", None)
        custom_success = getattr(endpoint, "_custom_success", None)
        custom_request_body = getattr(endpoint, "_request_body", None)

        for method_name in route.methods or []:
            method_lower = method_name.lower()
            path_item = openapi_schema["paths"].get(route.path, {})
            method_spec = path_item.get(method_lower, {})
            responses = method_spec.setdefault("responses", {})

            if custom_request_body and method_lower in ["post", "put", "patch"]:
                request_body = method_spec.setdefault("requestBody", {})
                content = request_body.setdefault("content", {})
                json_content = content.setdefault("application/json", {})
                custom_content = custom_request_body.get("content", {})
                custom_json = custom_content.get("application/json", {})
                custom_examples = custom_json.get("examples", {})

                if custom_examples:
                    json_content.setdefault("examples", {}).update(custom_examples)

            default_success_status = (
                custom_success.get("status_code")
                if custom_success
                else DEFAULT_SUCCESS_BY_METHOD.get(method_lower, 200)
            )
            success_description = (
                custom_success.get("description") if custom_success else "Successful Response"
            )

            existing_success = (
                openapi_schema["paths"]
                .get(route.path, {})
                .get(method_lower, {})
                .get("responses", {})
                .get(str(default_success_status), {})
            )
            existing_examples = (
                existing_success.get("content", {}).get("application/json", {}).get("examples")
            )

            responses[str(default_success_status)] = {
                "description": success_description,
                "content": {
                    "application/json": {
                        "schema": SuccessResponseModel.model_json_schema(),
                        "examples": existing_examples or {},
                    }
                },
            }

            error_codes = custom_errors or ERROR_MAP.get(method_lower, [])
            for code in error_codes:
                responses.setdefault(
                    code,
                    {
                        "description": "Standardized Error Response",
                        "content": {
                            "application/json": {"schema": ErrorResponseModel.model_json_schema()}
                        },
                    },
                )

    app.openapi_schema = openapi_schema
    return app.openapi_schema
