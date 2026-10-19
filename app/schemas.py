from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ErrorDetail(CamelModel):
    code: str
    message: str
    correlation_id: str


class ErrorResponse(CamelModel):
    error: ErrorDetail


class HealthResponse(CamelModel):
    status: str
    database_status: str
