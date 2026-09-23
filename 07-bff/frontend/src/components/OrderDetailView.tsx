import { useEffect, useState } from 'react'
import { OrderDetail } from '../types'

interface OrderDetailViewProps {
  initialOrderId?: number
  onBack?: () => void
}

export function OrderDetailView({ initialOrderId = 1, onBack }: OrderDetailViewProps) {
  const [orderId, setOrderId] = useState<number>(initialOrderId)
  const [order, setOrder] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [responseTime, setResponseTime] = useState<number | null>(null)

  const fetchOrderDetail = async (id: number) => {
    setLoading(true)
    setError(null)
    const start = performance.now()
    try {
      const res = await fetch(`/bff/orders/${id}`)
      if (!res.ok) {
        const errData = await res.json().catch(() => null)
        throw new Error(errData?.error || `HTTP ${res.status}`)
      }
      const data: OrderDetail = await res.json()
      setOrder(data)
      setResponseTime(Math.round(performance.now() - start))
    } catch (err) {
      setError(String(err))
      setOrder(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOrderDetail(orderId)
  }, [orderId])

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
    <div className="order-detail-container">
      {/* Header & Selector */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="detail-top-nav">
              {onBack && (
                <button className="btn btn-secondary btn-sm" onClick={onBack}>
                  ← Voltar para lista
                </button>
              )}
              <h2>Detalhes do Pedido #{orderId}</h2>
            </div>
            <p className="section-desc">
              Consumindo <code>GET /bff/orders/{orderId}</code> (composição de 3 microsserviços)
            </p>
          </div>

          <div className="header-actions">
            {responseTime !== null && !loading && (
              <span className="timing-pill">⚡ {responseTime}ms (1 request)</span>
            )}
            <button
              className="btn"
              onClick={() => fetchOrderDetail(orderId)}
              disabled={loading}
            >
              {loading ? 'Carregando…' : '↻ Recarregar'}
            </button>
          </div>
        </div>

        {/* Quick order switcher */}
        <div className="order-switcher">
          <span className="switcher-label">Selecionar pedido de teste:</span>
          <div className="switcher-buttons">
            {[1, 2, 3, 4, 5].map((id) => (
              <button
                key={id}
                className={`switcher-btn ${orderId === id ? 'switcher-btn-active' : ''}`}
                onClick={() => setOrderId(id)}
              >
                Pedido #{id}
              </button>
            ))}
          </div>
        </div>

        {/* Architecture Value Callout */}
        <div className="architecture-banner">
          <span className="banner-icon">🎯</span>
          <div>
            <strong>Padrão BFF em Ação:</strong> Esta página inteira foi montada a partir de <strong>uma única chamada HTTP</strong> ao BFF.
            O BFF buscou o pedido no <code>order-service</code>, o cliente no <code>user-service</code> e os produtos no <code>product-service</code> em paralelo.
          </div>
        </div>

        {error && (
          <div className="error-box">
            <span className="error-icon">⚠️</span>
            <div>
              <strong>Erro ao buscar pedido:</strong> {error}
            </div>
          </div>
        )}

        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Carregando dados compostos do pedido #{orderId}…</p>
          </div>
        ) : order ? (
          <div className="detail-content">
            {/* Top Stats Grid */}
            <div className="detail-grid">
              {/* Order Info */}
              <div className="detail-card">
                <div className="detail-card-title">
                  <span>📦 Dados do Pedido</span>
                  <span className="source-tag">order-service</span>
                </div>
                <div className="detail-field">
                  <span className="field-label">Identificador:</span>
                  <span className="field-value font-mono">#{order.order_id}</span>
                </div>
                <div className="detail-field">
                  <span className="field-label">Status:</span>
                  <div className="field-value">
                    <span className={`badge ${getStatusBadgeClass(order.status)}`}>
                      {order.status}
                    </span>
                    {order.is_degraded && (
                      <span className="badge badge-degraded">Degradado</span>
                    )}
                  </div>
                </div>
                <div className="detail-field">
                  <span className="field-label">Valor Total:</span>
                  <span className="field-value total-highlight">
                    R$ {order.total.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              {/* Customer Info */}
              <div className="detail-card">
                <div className="detail-card-title">
                  <span>👤 Dados do Cliente</span>
                  <span className="source-tag">user-service</span>
                </div>
                <div className="detail-field">
                  <span className="field-label">Nome:</span>
                  <span className="field-value">{order.customer.name}</span>
                </div>
                <div className="detail-field">
                  <span className="field-label">E-mail:</span>
                  <span className="field-value font-mono">{order.customer.email}</span>
                </div>
              </div>
            </div>

            {/* Items Table */}
            <div className="items-section">
              <div className="detail-card-title">
                <span>🛒 Itens do Pedido ({order.items.length})</span>
                <span className="source-tag">product-service</span>
              </div>
              <div className="table-responsive">
                <table className="orders-table">
                  <thead>
                    <tr>
                      <th>Produto ID</th>
                      <th>Nome do Produto</th>
                      <th>Preço Unitário</th>
                      <th>Quantidade</th>
                      <th>Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((item, idx) => {
                      const subtotal = item.price * item.quantity
                      return (
                        <tr key={idx}>
                          <td>
                            <span className="font-mono">#{item.product_id}</span>
                          </td>
                          <td>
                            <strong>{item.product_name}</strong>
                          </td>
                          <td>
                            R$ {item.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td>{item.quantity}x</td>
                          <td>
                            <span className="order-total">
                              R$ {subtotal.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

