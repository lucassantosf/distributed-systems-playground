import { useEffect, useState } from 'react'
import { OrderSummary } from '../types'

interface OrdersListProps {
  onSelectOrder?: (orderId: number) => void
}

export function OrdersList({ onSelectOrder }: OrdersListProps) {
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [responseTime, setResponseTime] = useState<number | null>(null)

  const fetchOrders = async () => {
    setLoading(true)
    setError(null)
    const start = performance.now()
    try {
      const res = await fetch('/bff/orders')
      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(errData?.error || `HTTP ${res.status}`)
      }
      const data: OrderSummary[] = await res.json()
      setOrders(data)
      setResponseTime(Math.round(performance.now() - start))
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOrders()
  }, [])

  const getStatusBadgeClass = (status: string) => {
    switch (status.toLowerCase()) {
      case 'confirmed':
        return 'badge-confirmed'
      case 'shipped':
        return 'badge-shipped'
      case 'delivered':
        return 'badge-delivered'
      case 'pending':
        return 'badge-pending'
      default:
        return 'badge-default'
    }
  }

  return (
    <div className="orders-container">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Lista de Pedidos</h2>
            <p className="section-desc">
              Consumindo <code>GET /bff/orders</code> (composição de <code>order-service</code> + <code>user-service</code>)
            </p>
          </div>
          <div className="header-actions">
            {responseTime !== null && !loading && (
              <span className="timing-pill">⚡ {responseTime}ms (1 request)</span>
            )}
            <button className="btn" onClick={fetchOrders} disabled={loading}>
              {loading ? 'Carregando…' : '↻ Recarregar'}
            </button>
          </div>
        </div>

        <div className="architecture-banner">
          <span className="banner-icon">💡</span>
          <div>
            <strong>Padrão API Composition:</strong> O frontend faz apenas <strong>1 chamada HTTP</strong>. O BFF orquestra as chamadas internas ao <code>order-service</code> (para obter a lista de pedidos) e ao <code>user-service</code> (para associar os nomes dos clientes), entregando o payload pronto para renderização.
          </div>
        </div>

        {error && (
          <div className="error-box">
            <span className="error-icon">⚠️</span>
            <div>
              <strong>Erro ao carregar pedidos:</strong> {error}
            </div>
          </div>
        )}

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Carregando pedidos via BFF…</p>
          </div>
        ) : orders.length === 0 && !error ? (
          <div className="empty-state">Nenhum pedido encontrado.</div>
        ) : (
          <div className="table-responsive">
            <table className="orders-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Cliente</th>
                  <th>Status</th>
                  <th>Itens</th>
                  <th>Total</th>
                  {onSelectOrder && <th>Ação</th>}
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.order_id}>
                    <td>
                      <span className="order-id">#{order.order_id}</span>
                    </td>
                    <td>
                      <div className="customer-cell">
                        <span className="customer-name">{order.customer_name}</span>
                        <span className="user-id-sub">User ID: {order.user_id}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(order.status)}`}>
                        {order.status}
                      </span>
                      {order.is_degraded && (
                        <span className="badge badge-degraded" title="Dados parcialmente degradados">
                          degradado
                        </span>
                      )}
                    </td>
                    <td>{order.items_count} {order.items_count === 1 ? 'item' : 'itens'}</td>
                    <td>
                      <strong className="order-total">
                        R$ {order.total.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </strong>
                    </td>
                    {onSelectOrder && (
                      <td>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => onSelectOrder(order.order_id)}
                        >
                          Ver Detalhes →
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

