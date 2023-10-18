"""
Enum by name to use in config.

See https://github.com/pydantic/pydantic/discussions/2980
"""
from enum import Enum

# from pydantic import GetJsonSchemaHandler
# from pydantic_core import CoreSchema


class EnumByName(Enum):
    """A custom Enum type for pydantic to validate by name."""

    @classmethod
    def __get_validators__(cls):
        # yield our validator
        yield cls._validate

    # I'm not sure if this is needed or not
    # @classmethod
    # def __get_pydantic_json_schema__(
    #   cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    # ) -> dict[str, Any]:
    #   json_schema = super().__get_pydantic_json_schema__(core_schema, handler)
    #   json_schema = handler.resolve_ref_schema(json_schema)
    #   json_schema.update(enum=list(cls.__members__.keys()))
    #   return json_schema

    @classmethod
    def _validate(cls, v, _):
        """Validate enum reference, `v`.

        We check:
          1. If it is a member of this Enum
          2. If we can find it by name.
        """
        # is the value an enum member?
        try:
            if v in cls:
                return v
        except TypeError:
            pass

        # not a member...look up by name
        try:
            return cls[v]
        except KeyError:
            name = cls.__name__
            expected = list(cls.__members__.keys())
            raise ValueError(
                f"{v} not found for enum {name}. Expected one of: {expected}",
            ) from None
