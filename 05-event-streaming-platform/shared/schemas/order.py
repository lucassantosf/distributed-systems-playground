"""
Modelos de domínio para pedidos (Order).

Representa a estrutura de um pedido e seus itens.
Usado como payload dentro dos eventos OrderCreated e OrderUpdated.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    """Um item dentro de um pedido."""

    product_id: str = Field(..., description="ID único do produto")
    product_name: str = Field(..., description="Nome do produto")
    quantity: int = Field(..., gt=0, description="Quantidade — deve ser maior que zero")
    unit_price: Decimal = Field(..., gt=0, description="Preço unitário em BRL")

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderCreatedPayload(BaseModel):
    """
    Payload do evento OrderCreated.
    Representa o estado completo do pedido no momento da criação.
    """

    customer_id: str = Field(..., description="ID único do cliente")
    customer_email: str = Field(..., description="E-mail do cliente")
    items: list[OrderItem] = Field(..., min_length=1, description="Itens do pedido")
    total_amount: Decimal = Field(..., gt=0, description="Valor total do pedido em BRL")
    currency: str = Field(default="BRL", description="Moeda do pedido")
    status: str = Field(default="pending", description="Status inicial do pedido")


class OrderUpdatedPayload(BaseModel):
    """
    Payload do evento OrderUpdated.
    Contém apenas os campos que podem ser atualizados após a criação.
    Seguindo o princípio de eventos de mudança de estado (delta).
    """

    previous_status: str = Field(..., description="Status anterior do pedido")
    new_status: str = Field(..., description="Novo status do pedido")
    reason: str | None = Field(default=None, description="Motivo da atualização (opcional)")


class InventoryReservedPayload(BaseModel):
    """
    Payload do evento InventoryReserved.
    Publicado pelo inventory-consumer após reservar estoque (Card 25).
    Demonstra o padrão de consumidor que também é produtor.
    """

    items_reserved: list[OrderItem] = Field(..., description="Itens com estoque reservado")
    warehouse_id: str = Field(default="WH-001", description="ID do armazém que fez a reserva")
