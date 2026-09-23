import { useEffect, useState } from 'react'
import './App.css'
import { ComparisonView } from './components/ComparisonView'
import { OrderDetailView } from './components/OrderDetailView'
import { OrdersList } from './components/OrdersList'
import { DownstreamHealth } from './types'

type HealthStatus = 'checking' | 'ok' | 'error'
type ActiveTab = 'orders' | 'detail' | 'comparison' | 'health'

function StatusBadge({ status }: { status: string }) {
  const isOk = status === 'ok'
  return (
    <span className={`badge ${isOk ? 'badge-ok' : 'badge-error'}`}>
      {isOk ? '✓ ok' : '✗ ' + status}
    </span>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('orders')
  const [selectedOrderId, setSelectedOrderId] = useState<number>(1)
  const [bffStatus, setBffStatus] = useState<HealthStatus>('checking')
  const [downstream, setDownstream] = useState<DownstreamHealth | null>(null)
  const [downstreamError, setDownstreamError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  const checkHealth = async () => {
    setBffStatus('checking')
    setDownstream(null)
    setDownstreamError(null)

    try {
      const res = await fetch('/health')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setBffStatus('ok')
    } catch {
      setBffStatus('error')
    }

    try {
      const res = await fetch('/health/downstream')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: DownstreamHealth = await res.json()
      setDownstream(data)
    } catch (err) {
      setDownstreamError(String(err))
    }

    setLastChecked(new Date().toLocaleTimeString('pt-BR'))
  }

  useEffect(() => {
    if (activeTab === 'health') {
      checkHealth()
    }
  }, [activeTab])

  const handleSelectOrder = (id: number) => {
    setSelectedOrderId(id)
    setActiveTab('detail')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">⚡</span>
            <div>
              <span className="logo-text">BFF Playground</span>
              <span className="logo-badge">Backend For Frontend</span>
            </div>
          </div>
          <nav className="nav-tabs">
            <button
              className={`nav-tab ${activeTab === 'orders' ? 'nav-tab-active' : ''}`}
              onClick={() => setActiveTab('orders')}
            >
              📦 Lista de Pedidos
            </button>
            <button
              className={`nav-tab ${activeTab === 'detail' ? 'nav-tab-active' : ''}`}
              onClick={() => setActiveTab('detail')}
            >
              🔍 Detalhe do Pedido
            </button>
            <button
              className={`nav-tab ${activeTab === 'comparison' ? 'nav-tab-active' : ''}`}
              onClick={() => setActiveTab('comparison')}
            >
              ⚡ BFF vs Direto
            </button>
            <button
              className={`nav-tab ${activeTab === 'health' ? 'nav-tab-active' : ''}`}
              onClick={() => setActiveTab('health')}
            >
              🩺 Status &amp; Health
              {bffStatus === 'ok' && <span className="tab-indicator-ok"></span>}
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
        {activeTab === 'orders' && (
          <OrdersList onSelectOrder={handleSelectOrder} />
        )}

        {activeTab === 'detail' && (
          <OrderDetailView
            initialOrderId={selectedOrderId}
            onBack={() => setActiveTab('orders')}
          />
        )}

        {activeTab === 'comparison' && (
          <ComparisonView />
        )}

        {activeTab === 'health' && (
          <div className="health-container">
            <section className="card">
              <div className="card-header">
                <h2>BFF Status</h2>
                <button className="btn" onClick={checkHealth}>
                  ↻ Verificar
                </button>
              </div>

              <div className="status-row">
                <span className="service-name">bff</span>
                {bffStatus === 'checking' ? (
                  <span className="badge badge-checking">verificando…</span>
                ) : (
                  <StatusBadge status={bffStatus === 'ok' ? 'ok' : 'error'} />
                )}
                <code className="endpoint">GET /health</code>
              </div>

              {lastChecked && (
                <p className="last-checked">Última verificação: {lastChecked}</p>
              )}
            </section>

            <section className="card">
              <div className="card-header">
                <h2>Serviços Downstream</h2>
                {downstream && <StatusBadge status={downstream.status} />}
              </div>

              {downstreamError && (
                <p className="error-msg">Erro ao conectar ao BFF: {downstreamError}</p>
              )}

              {downstream ? (
                <div className="services-list">
                  {Object.entries(downstream.downstream).map(([name, info]) => (
                    <div key={name} className="status-row">
                      <span className="service-name">{name}</span>
                      <StatusBadge status={info.status} />
                      {info.http_status && (
                        <code className="endpoint">HTTP {info.http_status}</code>
                      )}
                      {info.detail && (
                        <code className="endpoint error-detail">{info.detail}</code>
                      )}
                    </div>
                  ))}
                </div>
              ) : !downstreamError ? (
                <p className="checking-msg">Consultando serviços…</p>
              ) : null}
            </section>

            <section className="card info-card">
              <h2>Endpoints disponíveis</h2>
              <table className="endpoints-table">
                <thead>
                  <tr>
                    <th>Endpoint</th>
                    <th>Descrição</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code>GET /bff/orders</code></td>
                    <td>Listagem de pedidos (order + user)</td>
                  </tr>
                  <tr>
                    <td><code>GET /bff/orders/{'{id}'}</code></td>
                    <td>Detalhe do pedido (order + user + products)</td>
                  </tr>
                  <tr>
                    <td><code>GET /bff/users/{'{id}'}/orders</code></td>
                    <td>Pedidos por cliente</td>
                  </tr>
                  <tr>
                    <td><code>GET /health/downstream</code></td>
                    <td>Status dos serviços downstream</td>
                  </tr>
                </tbody>
              </table>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}
