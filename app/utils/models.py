from pydantic import BaseModel, Field


class HTTPError(BaseModel):
    error_code: int = Field(
        description="Error code",
        frozen=True,
    )

    detail: str = Field(
        description="Error message",
        frozen=True,
    )


class Hint(BaseModel):
    hint: str | None
