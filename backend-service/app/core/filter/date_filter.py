from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class DateFilter(BaseModel):
    """
    DateFilter for createdAt filtering.
    from: ISO 8601 date-time, inclusive lower bound
    to: ISO 8601 date-time, inclusive upper bound
    Null or empty means no date restriction.
    """

    from_: Optional[datetime] = Field(default=None, alias="from")
    to: Optional[datetime] = Field(default=None)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateFilter":
        if self.from_ is not None and self.to is not None:
            if self.from_ > self.to:
                raise ValueError("'from' date cannot be after 'to' date")
        return self
