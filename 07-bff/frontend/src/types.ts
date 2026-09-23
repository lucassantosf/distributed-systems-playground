export interface OrderSummary {
  order_id: number
  user_id: number
  customer_name: string
  status: string
  total: number
  items_count: number
  is_degraded?: boolean
}

export interface CustomerInfo {
  name: string
  email: string
}

export interface OrderItemDetail {
  product_id: number
  product_name: string
  price: number
  quantity: number
}

export interface OrderDetail {
  order_id: number
  status: string
  total: number
  customer: CustomerInfo
  items: OrderItemDetail[]
  is_degraded?: boolean
}

export interface DownstreamService {
  status: string
  http_status?: number
  detail?: string
}

export interface DownstreamHealth {
  status: string
  downstream: Record<string, DownstreamService>
}
