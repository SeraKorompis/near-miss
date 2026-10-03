import { useEffect, useState } from 'react'
import { History } from './History'
import { LiveFloor } from './LiveFloor'

export function App() {
  const [tab, setTab] = useState(() => (window.location.hash === '#history' ? 'history' : 'live'))

  useEffect(() => {
    const sync = () => setTab(window.location.hash === '#history' ? 'history' : 'live')
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  function open(next) {
    window.location.hash = next === 'history' ? '#history' : '#live'
    setTab(next)
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden="true">IS</span>
          <div>
            <h1>INstoreSIGHT</h1>
            <p className="tagline">The sale you are about to lose, and the move that wins it back.</p>
          </div>
        </div>
        <nav className="tabs" aria-label="Dashboards">
          <button type="button" aria-selected={tab === 'live'} onClick={() => open('live')}>
            Live floor
          </button>
          <button type="button" data-testid="tab-history" aria-selected={tab === 'history'} onClick={() => open('history')}>
            History
          </button>
        </nav>
      </header>
      <main>
        <div hidden={tab !== 'live'}>
          <LiveFloor />
        </div>
        <div hidden={tab !== 'history'}>
          <History />
        </div>
      </main>
    </div>
  )
}
