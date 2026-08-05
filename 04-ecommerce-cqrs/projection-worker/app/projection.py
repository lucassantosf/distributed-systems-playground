from shared.events.product import PRODUCT_CREATED, PRODUCT_UPDATED
from shared.schemas.read_models.product import ProductReadModel


def _format_price(price: float) -> str:
    value = f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value}"


def _price_tier(price: float) -> str:
    if price < 200:
        return "low"
    if price < 1000:
        return "medium"
    return "high"


def _build_product_read_model(event: dict) -> ProductReadModel:
    return ProductReadModel(
        id=event["product_id"],
        name=event["name"],
        price=event["price"],
        category=event["category"],
        in_stock=event["stock"] > 0,
        formatted_price=_format_price(event["price"]),
        price_tier=_price_tier(event["price"]),
        name_normalized=event["name"].lower(),
    )


def build_read_model(event: dict) -> ProductReadModel:
    event_type = event.get("event")
    if event_type in (PRODUCT_CREATED, PRODUCT_UPDATED):
        return _build_product_read_model(event)
    return event
