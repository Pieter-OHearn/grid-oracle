from pydantic import BaseModel


class DriverItem(BaseModel):
    code: str
    full_name: str
    number: int | None = None
    constructor: str
    constructor_color: str
    nationality: str
    flag: str
