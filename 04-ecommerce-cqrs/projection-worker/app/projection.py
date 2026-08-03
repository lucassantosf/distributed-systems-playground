def build_read_model(event: dict) -> dict:
    event_type = event.get("event")
    if event_type == "ProductCreated":
        return {
            "id": event["product_id"],
            "name": event["name"],
            "price": event["price"],
            "category": event["category"],
            "in_stock": event["stock"] > 0,
        }
    return event
