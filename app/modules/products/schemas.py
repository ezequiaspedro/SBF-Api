from typing import List, Optional
from ...utils.helpers import BaseSchema, MetaDatetimeSchema
from ...utils.pagination import PaginationMetadataSchema


class ProductCreate(BaseSchema):
    name: str
    size: str
    inventory: int
    weight: float

    class Config:
        schema_extra = {
            "example": {
                "name": "Camisa Azul",
                "size": "P",
                "inventory": 10,
                "weight": 10.5
            }
        }
    
class ProductUpdate(BaseSchema):
    name: Optional[str]
    size: Optional[str]
    weight: Optional[float]

    class Config:
        schema_extra = {
            "example": {
                "name": "Camisa Azul",
                "size": "P",
                "weight": 10.5
            }
        }

class ProductResponse(BaseSchema):
    id: int
    name: str
    size: str
    inventory: int
    weight: float
    metadatetime: MetaDatetimeSchema

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Camisa Amarela",
                "size": "P",
                "inventory": 10,
                "weight": 10.5,
                "metadatetime": {
                    "created_on": "2020-01-01T00:00:00.000001",
                    "updated_on": "2020-01-01T00:00:00.000001"
                }
            }
        }

class ProductsResponse(BaseSchema):
    pagination_metadata: Optional[PaginationMetadataSchema]
    records: List[ProductResponse]