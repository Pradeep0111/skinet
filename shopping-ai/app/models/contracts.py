from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel

JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda value: float(value), return_type=float, when_used="json"),
]


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class NutritionFacts(ContractModel):
    serving_size: str | None = None
    calories: JsonDecimal | None = Field(default=None, ge=0)
    protein: JsonDecimal | None = Field(default=None, ge=0)
    carbohydrates: JsonDecimal | None = Field(default=None, ge=0)
    fat: JsonDecimal | None = Field(default=None, ge=0)
    fiber: JsonDecimal | None = Field(default=None, ge=0)
    sugar: JsonDecimal | None = Field(default=None, ge=0)
    sodium: JsonDecimal | None = Field(default=None, ge=0)


class Promotion(ContractModel):
    sale_price: JsonDecimal = Field(ge=0)
    label: str
    starts_at: str | None = None
    ends_at: str | None = None


class AssistantProduct(ContractModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    description: str
    price: JsonDecimal = Field(ge=0)
    effective_price: JsonDecimal = Field(ge=0)
    picture_url: str
    brand: str
    type: str
    category: str | None = None
    subcategory: str | None = None
    quantity_in_stock: int = Field(ge=0)
    sku: str | None = None
    unit_size: JsonDecimal | None = Field(default=None, gt=0)
    unit_label: str | None = None
    tags: list[str] = Field(default_factory=list)
    dietary_labels: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    ingredients: str | None = None
    nutrition: NutritionFacts | None = None
    origin: str | None = None
    storage_instructions: str | None = None
    shelf_life_days: int | None = Field(default=None, ge=0)
    average_rating: JsonDecimal | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    promotion: Promotion | None = None
    substitution_group: str | None = None


class CatalogPage(ContractModel):
    page_index: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    count: int = Field(ge=0)
    data: list[AssistantProduct] = Field(default_factory=list)


class StockCheck(ContractModel):
    product_id: int = Field(gt=0)
    requested_quantity: int = Field(gt=0, le=99)
    quantity_in_stock: int = Field(ge=0)
    available: bool


class ChatRequest(ContractModel):
    message: str = Field(min_length=1, max_length=1_000)
    conversation_id: str | None = None
    cart_id: str | None = None


class CartContextItem(ContractModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=99)


class CartContext(ContractModel):
    items: list[CartContextItem] = Field(default_factory=list, max_length=100)


class ProductPreference(ContractModel):
    product_id: int = Field(gt=0)
    purchase_count: int = Field(gt=0)
    last_purchased_at: datetime | None = None


class ShopperContext(ContractModel):
    is_authenticated: bool = False
    preferences: list[ProductPreference] = Field(default_factory=list, max_length=100)


class InternalChatRequest(ContractModel):
    message: str = Field(min_length=1, max_length=1_000)
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    cart: CartContext | None = None
    shopper: ShopperContext | None = None


class ProductComparison(ContractModel):
    title: str
    product_ids: list[int] = Field(min_length=2)
    summary: str


class ProposedAction(ContractModel):
    action_id: str = Field(min_length=1)
    action_type: Literal["add_to_cart"]
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=99)
    label: str
    requires_confirmation: Literal[True] = True


class ChatResponse(ContractModel):
    conversation_id: str = Field(min_length=1)
    message: str
    products: list[AssistantProduct] = Field(default_factory=list)
    comparisons: list[ProductComparison] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)


class ErrorResponse(ContractModel):
    error_code: str
    message: str
    retryable: bool = False
    correlation_id: str
