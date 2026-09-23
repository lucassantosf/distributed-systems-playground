import { useState } from 'react'
import { CustomerInfo, OrderDetail, OrderItemDetail } from '../types'

interface CallRecord {
  url: string
  durationMs: number
  status: number
}

interface ApproachResult {
  orderDetail: OrderDetail | null
  calls: CallRecord[]
  totalMs: number
  error: string | null
}

const EMPTY_RESULT: ApproachResult = {
  orderDetail: null,
  calls: [],
  totalMs: 0,
  error: null,
}

// ─── BFF approach ────────────────────────────────────────────────────────────
async function loadViaBff(orderId: number): Promise<ApproachResult> {
  const calls: CallRecord[] = []
  const globalStart = performance.now()
  try {
    const callStart = performance.now()
    const res = await fetch(`/bff/orders/${orderId}`)
    const durationMs = Math.round(performance.now() - callStart)
    const status = res.status
    calls.push({ url: `/bff/orders/${orderId}`, durationMs, status })

    if (!res.ok) {
      const errData = await res.json().catch(() => null)
      throw new Error(errData?.error || `HTTP ${status}`)
    }
    const data: OrderDetail = await res.json()
    return { orderDetail: data, calls, totalMs: Math.round(performance.now() - globalStart), error: null }
  } catch (err) {
    return { ...EMPTY_RESULT, calls, totalMs: Math.round(performance.now() - globalStart), error: String(err) }
  }
}

// ─── Direct approach ──────────────────────────────────────────────────────────
async function loadDirectly(orderId: number): Promise<ApproachResult> {
  const calls: CallRecord[] = []
  const globalStart = performance.now()

  try {
    // Call 1: order-service
    const t1 = performance.now()
    const orderRes = await fetch(`/direct/orders/${orderId}`)
    calls.push({ url: `/direct/orders/${orderId}`, durationMs: Math.round(performance.now() - t1), status: orderRes.status })
    if (!orderRes.ok) throw new Error(`order-service HTTP ${orderRes.status}`)
    const rawOrder = await orderRes.json()

    // Call 2: user-service
    const t2 = performance.now()
    const userRes = await fetch(`/direct/users/${rawOrder.user_id}`)
    calls.push({ url: `/direct/users/${rawOrder.user_id}`, durationMs: Math.round(performance.now() - t2), status: userRes.status })
    if (!userRes.ok) throw new Error(`user-service HTTP ${userRes.status}`)
    const rawUser = await userRes.json()

    // Calls 3..N: product-service (sequential — as a naive client would do)
    const productItems: OrderItemDetail[] = []
    for (const item of rawOrder.items as { product_id: number; quantity: number }[]) {
      const tp = performance.now()
      const prodRes = await fetch(`/direct/products/${item.product_id}`)
      calls.push({
        url: `/direct/products/${item.product_id}`,
        durationMs: Math.round(performance.now() - tp),
        status: prodRes.status,
      })
      if (!prodRes.ok) throw new Error(`product-service HTTP ${prodRes.status}`)
      const rawProd = await prodRes.json()
      productItems.push({
        product_id: rawProd.id,
        product_name: rawProd.name,
        price: rawProd.price,
        quantity: item.quantity,
      })
    }

    // Assemble the same shape as OrderDetail
    const customer: CustomerInfo = { name: rawUser.name, email: rawUser.email }
    const assembled: OrderDetail = {
      order_id: rawOrder.id,
      status: rawOrder.status,
      total: rawOrder.total,
      customer,
      items: productItems,
      is_degraded: false,
    }

    return {
      orderDetail: assembled,
      calls,
      totalMs: Math.round(performance.now() - globalStart),
      error: null,
    }
  } catch (err) {
    return { ...EMPTY_RESULT, calls, totalMs: Math.round(performance.now() - globalStart), error: String(err) }
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function CallLog({ calls }: { calls: CallRecord[] }) {
  return (
    <div className="call-log">
      {calls.map((c, i) => (
        <div key={i} className="call-log-row">
          <span className="call-number">#{i + 1}</span>
          <span className="call-method">GET</span>
          <code className="call-url">{c.url}</code>
          <span className={`call-status ${c.status < 400 ? 'call-ok' : 'call-err'}`}>
            {c.status}
          </span>
          <span className="call-time">{c.durationMs}ms</span>
        </div>
      ))}
    </div>
  )
}

function ResultPanel({
  label,
  tagline,
  labelColor,
  result,
  loading,
  onLoad,
  orderId,
}: {
  label: string
  tagline: string
  labelColor: string
  result: ApproachResult
  loading: boolean
  onLoad: () => void
  orderId: number
}) {
  const { orderDetail: order, calls, totalMs, error } = result

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'confirmed': return 'badge-confirmed'
      case 'shipped': return 'badge-shipped'
      case 'delivered': return 'badge-delivered'
      case 'pending': return 'badge-pending'
      default: return ''
    }
  }

  return (
    <div className="comparison-panel">
      <div className="panel-header" style={{ borderColor: labelColor }}>
        <div>
          <div className="panel-title" style={{ color: labelColor }}>{label}</div>
          <div className="panel-tagline">{tagline}</div>
        </div>
        <button className="btn" onClick={onLoad} disabled={loading}>
          {loading ? 'Carregando…' : `▶ Testar Pedido #${orderId}`}
        </button>
      </div>

      {/* Stats row */}
      {calls.length > 0 && (
        <div className="stats-row">
          <div className="stat-box">
            <span className="stat-value" style={{ color: labelColor }}>{calls.length}</span>
            <span className="stat-label">chamada{calls.length !== 1 ? 's' : ''} HTTP</span>
          </div>
          <div className="stat-box">
            <span className="stat-value">{totalMs}ms</span>
            <span className="stat-label">tempo total</span>
          </div>
        </div>
      )}

      {/* Call log */}
      {calls.length > 0 && (
        <div className="panel-section">
          <div className="panel-section-title">📡 Chamadas realizadas</div>
          <CallLog calls={calls} />
        </div>
      )}

      {error && (
        <div className="error-box" style={{ marginTop: '0.75rem' }}>
          <span>⚠️</span>
          <div>{error}</div>
        </div>
      )}

      {loading && (
        <div className="loading-state" style={{ padding: '2rem' }}>
          <div className="spinner"></div>
          <p>Fazendo chamadas…</p>
        </div>
      )}

      {/* Result */}
      {order && !loading && (
        <div className="panel-section">
          <div className="panel-section-title">📋 Resultado montado</div>
          <div className="result-order">
            <div className="result-row">
              <span className="result-label">Pedido</span>
              <span className="result-value font-mono">#{order.order_id}</span>
            </div>
            <div className="result-row">
              <span className="result-label">Status</span>
              <span className={`badge ${getStatusBadgeClass(order.status)}`}>{order.status}</span>
            </div>
            <div className="result-row">
              <span className="result-label">Cliente</span>
              <span className="result-value">{order.customer.name}</span>
            </div>
            <div className="result-row">
              <span className="result-label">Email</span>
              <span className="result-value font-mono" style={{ fontSize: '0.8rem' }}>{order.customer.email}</span>
            </div>
            <div className="result-divider">Itens</div>
            {order.items.map((item, i) => (
              <div key={i} className="result-item">
                <span className="result-item-name">{item.product_name}</span>
                <span className="result-item-qty">{item.quantity}x</span>
                <span className="result-item-price">
                  R$ {(item.price * item.quantity).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
              </div>
            ))}
            <div className="result-total">
              <span>Total</span>
              <span className="order-total">R$ {order.total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────
export function ComparisonView() {
  const [orderId, setOrderId] = useState(1)
  const [bffResult, setBffResult] = useState<ApproachResult>(EMPTY_RESULT)
  const [directResult, setDirectResult] = useState<ApproachResult>(EMPTY_RESULT)
  const [loadingBff, setLoadingBff] = useState(false)
  const [loadingDirect, setLoadingDirect] = useState(false)

  const handleBff = async () => {
    setLoadingBff(true)
    const result = await loadViaBff(orderId)
    setBffResult(result)
    setLoadingBff(false)
  }

  const handleDirect = async () => {
    setLoadingDirect(true)
    const result = await loadDirectly(orderId)
    setDirectResult(result)
    setLoadingDirect(false)
  }

  const handleBoth = async () => {
    setBffResult(EMPTY_RESULT)
    setDirectResult(EMPTY_RESULT)
    setLoadingBff(true)
    setLoadingDirect(true)
    const [b, d] = await Promise.all([loadViaBff(orderId), loadDirectly(orderId)])
    setBffResult(b)
    setDirectResult(d)
    setLoadingBff(false)
    setLoadingDirect(false)
  }

  const hasBoth = bffResult.calls.length > 0 && directResult.calls.length > 0

  return (
    <div className="comparison-container">
      <div className="card">
        <div className="card-header">
          <div>
            <h2>Demonstração do Valor do BFF</h2>
            <p className="section-desc">
              Mesmos dados, duas abordagens. Compare o número de chamadas HTTP e o tempo de resposta.
            </p>
          </div>
        </div>

        {/* Explanation banner */}
        <div className="comparison-explanation">
          <div className="explanation-col">
            <div className="explanation-title" style={{ color: '#4ade80' }}>✅ Via BFF</div>
            <p>O frontend faz <strong>1 chamada</strong> ao BFF. O BFF orquestra o resto internamente em paralelo, na rede Docker.</p>
          </div>
          <div className="explanation-divider">vs</div>
          <div className="explanation-col">
            <div className="explanation-title" style={{ color: '#fb923c' }}>⚠️ Sem BFF (direto)</div>
            <p>O frontend faz <strong>1 + 1 + N</strong> chamadas em sequência: pedido → cliente → produto por produto.</p>
          </div>
        </div>

        {/* Order selector + Run both */}
        <div className="comparison-controls">
          <div className="order-switcher" style={{ margin: 0 }}>
            <span className="switcher-label">Pedido de teste:</span>
            <div className="switcher-buttons">
              {[1, 2, 3, 4, 5].map((id) => (
                <button
                  key={id}
                  className={`switcher-btn ${orderId === id ? 'switcher-btn-active' : ''}`}
                  onClick={() => setOrderId(id)}
                >
                  #{id}
                </button>
              ))}
            </div>
          </div>
          <button
            className="btn btn-run-both"
            onClick={handleBoth}
            disabled={loadingBff || loadingDirect}
          >
            ⚡ Comparar Ambos Simultâneamente
          </button>
        </div>

        {/* Summary when both have results */}
        {hasBoth && (
          <div className="comparison-summary">
            <div className={`summary-item ${bffResult.calls.length < directResult.calls.length ? 'summary-winner' : ''}`}>
              <span className="summary-label">BFF — chamadas HTTP</span>
              <span className="summary-big" style={{ color: '#4ade80' }}>{bffResult.calls.length}</span>
            </div>
            <div className="summary-arrow">vs</div>
            <div className={`summary-item ${directResult.calls.length < bffResult.calls.length ? 'summary-winner' : ''}`}>
              <span className="summary-label">Direto — chamadas HTTP</span>
              <span className="summary-big" style={{ color: '#fb923c' }}>{directResult.calls.length}</span>
            </div>
            <div className="summary-arrow">|</div>
            <div className="summary-item">
              <span className="summary-label">Tempo BFF</span>
              <span className="summary-big" style={{ color: '#4ade80' }}>{bffResult.totalMs}ms</span>
            </div>
            <div className="summary-arrow">vs</div>
            <div className="summary-item">
              <span className="summary-label">Tempo Direto</span>
              <span className="summary-big" style={{ color: '#fb923c' }}>{directResult.totalMs}ms</span>
            </div>
          </div>
        )}
      </div>

      {/* Panels side by side */}
      <div className="comparison-panels">
        <ResultPanel
          label="🟢 Via BFF"
          tagline="1 endpoint, 1 chamada, dados compostos prontos"
          labelColor="#4ade80"
          result={bffResult}
          loading={loadingBff}
          onLoad={handleBff}
          orderId={orderId}
        />
        <ResultPanel
          label="🟠 Sem BFF (chamadas diretas)"
          tagline="Cada dado buscado pelo frontend separadamente"
          labelColor="#fb923c"
          result={directResult}
          loading={loadingDirect}
          onLoad={handleDirect}
          orderId={orderId}
        />
      </div>
    </div>
  )
}

