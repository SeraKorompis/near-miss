import { useEffect, useState } from 'react'
import { analyse, contrastProduct, formatTimer, liveRisk, pct } from './model'
import { useAisle } from './useAisle'

const week = analyse('week')

export function LiveFloor() {
  const aisle = useAisle()
  const { snap, playing, setPlaying, speed, setSpeed, feed } = aisle
  const shown = snap.activeId ? cardFor(snap.activeId) : null
  const liveOnly = snap.seen.filter((id) => !week.byId[id])
  const other = shown ? contrastProduct(shown.id, week.products) : null
  const risk = shown ? liveRisk(shown, snap.dwellMs) : 0
  const otherRisk = other ? liveRisk(other, snap.dwellMs) : 0
  const hot = risk >= 0.6 && snap.phase === 'gaze'
  const between = snap.phase !== 'gaze'
  const [cameraOn, setCameraOn] = useState(false)

  return (
    <section className="live">
      <div className="live-bar">
        <div>
          <p className="kicker">
            <span className={feed === 'live' ? 'dot live' : feed === 'mock' && playing ? 'dot' : 'dot idle'} />
            {feed === 'live' ? 'Live vision feed' : feed === 'done' ? 'Clip finished' : feed === 'error' ? 'Feed unavailable' : feed === 'mock' ? 'Sample aisle' : 'Waiting for the camera'}
            {feed === 'mock' && (
              <>
                {' '}
                · Shopper {snap.shoppersPlayed + 1}{between ? ' · moving on' : ''}
              </>
            )}
          </p>
          <p className="fine">
            {feed === 'live'
              ? 'The camera is sending the product it sees. The timer is that look’s dwell. A product that is not on the dummy shelf is added here anyway.'
              : feed === 'done'
                ? 'The clip has finished. Suggestions from the analysis are below.'
              : feed === 'mock'
                ? 'This is a scripted sample, not the camera. Start the vision demo and the live floor switches over.'
                : 'No looks yet. Glances, products and the timer stay at zero until the vision demo sends a product.'}
          </p>
        </div>
        {feed !== 'live' && (
          <div className="controls">
            <button
              type="button"
              onClick={() => {
                if (feed === 'waiting') aisle.playSample()
                else setPlaying((on) => !on)
              }}
            >
              {feed === 'waiting' ? 'Play sample' : playing ? 'Pause' : 'Play'}
            </button>
            <button type="button" onClick={aisle.nextShopper}>
              Next shopper
            </button>
            <button type="button" onClick={aisle.restart}>
              Replay
            </button>
            <div className="speeds" role="group" aria-label="Playback speed">
              {[1, 2, 4].map((value) => (
                <button key={value} type="button" aria-pressed={speed === value} onClick={() => setSpeed(value)}>
                  {value}×
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className={cameraOn ? 'live-stage' : undefined}>
      <CameraView onLive={setCameraOn} />
      <div className="heroes">
        <article className="hero">
          <p className="hero-label">Glances</p>
          <p className="hero-num" data-testid="glances-count">
            {snap.glances}
          </p>
          <p className="hero-note">Looks of 0.4s or more, this shopper</p>
        </article>
        <article className="hero">
          <p className="hero-label">Products</p>
          <p className="hero-num" data-testid="products-count">
            {snap.seen.length}
            <span> / {week.products.length + liveOnly.length}</span>
          </p>
          <p className="hero-note">Products looked at on this shelf</p>
        </article>
        <article className={hot ? 'hero dwell hot' : 'hero dwell'}>
          <p className="hero-label">{between && feed !== 'waiting' ? 'Between products' : 'Dwelling on one zone'}</p>
          <p className="hero-num timer" data-testid="dwell-timer">
            {formatTimer(between ? 0 : snap.dwellMs)}
          </p>
          <p className="hero-note">{shown ? shown.name : 'Timer resets when the look moves'}</p>
        </article>
      </div>
      </div>

      {snap.suggestions?.length > 0 && (
        <section className="suggestions" aria-label="Suggestions">
          <p className="kicker">From the analysis{snap.suggestionVideo ? ` · ${snap.suggestionVideo}` : ''}</p>
          <h2>What to try next</h2>
          <ol className="queue">
            {snap.suggestions.map((item, index) => (
              <li key={item.product} className={`priority-${item.priority || 'low'}`}>
                <p className="queue-index">{String(index + 1).padStart(2, '0')}</p>
                <div>
                  <p className="queue-action">{labelPriority(item.priority)}</p>
                  <h3>{humanize(item.product)}</h3>
                  <p>{item.diagnosis}</p>
                  <p className="math">{item.action}</p>
                </div>
                <div className="queue-value">
                  <strong>{item.near_misses}</strong>
                  <span>{item.near_misses === 1 ? 'near-miss' : 'near-misses'}</span>
                  <em>{item.purchases} bought · {Number(item.dwell_s).toFixed(1)}s attention</em>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="fixture" aria-label="Shelf">
        {liveOnly.length > 0 && (
          <section className="category-block">
            <h2 className="category">Seen on camera</h2>
            <div className="shelf">
              {liveOnly.map((id) => pack(cardFor(id), snap))}
            </div>
          </section>
        )}
        {[['Drinks', 'Drinks'], ['Snacks', 'Snacks'], ['Sauces', 'Sauces and other']].map(([category, label]) => (
        <section key={category} className="category-block">
        <h2 className="category">{label}</h2>
        <div className="shelf">
          {week.products.filter((product) => product.category === category).map((product) => pack(product, snap))}
        </div>
        </section>
        ))}
      </div>

      <div className="live-split">
        <article className={hot ? 'predict hot' : 'predict'}>
          <p className="kicker">Prediction · updates with the timer</p>
          {shown ? (
            <>
              <p className="risk" data-testid="near-miss-risk">
                {pct(risk)} <span>chance this look walks</span>
              </p>
              {other && (
                <p className="predict-copy">
                  Same {formatTimer(snap.dwellMs)} on {other.name} would be {pct(otherRisk)}. Products that usually sell have a lower ceiling, so a long look is not automatically a miss.
                </p>
              )}
              <p className="on-file">
                <strong>Buyer move on file · {shown.title}</strong>
                <span>{shown.next}</span>
              </p>
            </>
          ) : (
            <p className="predict-copy">Nobody is on a zone. The next look starts the timer again, and the prediction climbs only while they stay.</p>
          )}
        </article>

        <article className="log">
          <p className="kicker">This trip · {snap.demoGlances} glances in the demo</p>
          <ol>
            {snap.log.length === 0 && <li className="empty">The first look has not finished yet.</li>}
            {snap.log.map((entry) => {
              const product = week.byId[entry.productId]
              return (
                <li key={entry.id} className={entry.kind}>
                  <span className="log-kind">{labelFor(entry.kind)}</span>
                  <span className="log-what">
                    <strong>{product?.name || humanize(entry.productId)}</strong>
                    <em>{(entry.dwellMs / 1000).toFixed(1)}s</em>
                  </span>
                  <span className="log-why">{entry.text}</span>
                </li>
              )
            })}
          </ol>
        </article>
      </div>
    </section>
  )
}

function CameraView({ onLive }) {
  const [live, setLive] = useState(false)

  useEffect(() => {
    onLive(live)
  }, [live, onLive])

  useEffect(() => {
    let stopped = false
    const ping = async () => {
      const ctrl = new AbortController()
      const timer = window.setTimeout(() => ctrl.abort(), 700)
      try {
        const res = await fetch('http://127.0.0.1:8766/health', { signal: ctrl.signal, cache: 'no-store' })
        if (!stopped) setLive(res.ok)
      } catch {
        if (!stopped) setLive(false)
      } finally {
        window.clearTimeout(timer)
      }
    }
    ping()
    const id = window.setInterval(ping, 1000)
    return () => {
      stopped = true
      window.clearInterval(id)
    }
  }, [])

  if (!live) return null

  return (
    <figure className="camera">
      <img src="http://127.0.0.1:8766/video" alt="Annotated view from the vision pipeline" />
    </figure>
  )
}

function pack(product, snap) {
  const on = product.id === snap.activeId
  const flash = snap.flash?.productId === product.id ? snap.flash.kind : null
  const fill = on ? Math.min(100, (snap.dwellMs / 8000) * 100) : 0
  return (
    <div key={product.id} className={on ? 'pack on' : flash ? `pack ${flash}` : 'pack'}>
      <div className="pack-face">
        <i style={{ background: product.color }} />
        <span>{product.brand}</span>
        <strong title={product.name}>{product.short}</strong>
        {typeof product.price === 'number' && <em>£{product.price.toFixed(2)}</em>}
      </div>
      <div className="meter">
        <span style={{ width: `${fill}%` }} />
      </div>
      <small>{on && snap.touch ? 'Touching' : product.position}</small>
    </div>
  )
}

function cardFor(id) {
  const known = week.byId[id]
  if (known) return known
  const name = humanize(id)
  return {
    id,
    name,
    short: name,
    brand: 'Camera',
    color: hashColor(id),
    position: 'Live zone',
    walkAway: 0.7,
    title: 'No history yet',
    next: 'The camera is measuring this look. Dummy history does not include this product.',
  }
}

function labelPriority(priority) {
  const text = priority || 'low'
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function humanize(id) {
  const text = String(id).replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Unknown product'
}

function hashColor(id) {
  let hash = 0
  for (const char of String(id)) hash = (hash * 33 + char.charCodeAt(0)) >>> 0
  return `hsl(${hash % 360} 62% 52%)`
}

function labelFor(kind) {
  if (kind === 'miss') return 'Near-miss'
  if (kind === 'buy') return 'Purchase'
  if (kind === 'slide') return 'Slide-off'
  return 'Glance'
}
