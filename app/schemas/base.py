"""
Base Pydantic v2 model configuration for API schemas.
"""
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema enabling ORM compatibility and attribute population."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
