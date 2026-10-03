import { analyse, contrastProduct, formatTimer, liveRisk, pct } from './model'
import { useAisle } from './useAisle'

const week = analyse('week')

export function LiveFloor() {
  const aisle = useAisle()
  const { snap, playing, setPlaying, speed, setSpeed, feed } = aisle
  const active = snap.activeId ? week.byId[snap.activeId] : null
  const shown = active || (snap.activeId
    ? { id: snap.activeId, name: snap.activeId, brand: '', position: '', walkAway: 0.7, title: 'No history yet', next: 'The live feed sent this name. Dummy history does not include it yet.' }
    : null)
  const other = shown ? contrastProduct(shown.id, week.products) : null
  const risk = shown ? liveRisk(shown, snap.dwellMs) : 0
  const otherRisk = other ? liveRisk(other, snap.dwellMs) : 0
  const hot = risk >= 0.6 && snap.phase === 'gaze'
  const between = snap.phase !== 'gaze'

  return (
    <section className="live">
      <div className="live-bar">
        <div>
          <p className="kicker">
            <span className={feed === 'live' ? 'dot live' : playing ? 'dot' : 'dot idle'} />
            {feed === 'live' ? 'Live vision feed' : feed === 'connecting' ? 'Connecting feed' : feed === 'error' ? 'Feed unavailable' : 'Mock aisle'}
            {feed === 'mock' && (
              <>
                {' '}
                · Shopper {snap.shoppersPlayed + 1}{between ? ' · moving on' : ''}
              </>
            )}
          </p>
          <p className="fine">
            The vision model sends a product name. The timer runs while that name stays the same. No face is stored. Until the feed is connected, scripted looks play.
          </p>
        </div>
        {feed !== 'live' && (
          <div className="controls">
            <button type="button" onClick={() => setPlaying((on) => !on)}>
              {playing ? 'Pause' : 'Play'}
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
            <span> / {week.products.length}</span>
          </p>
          <p className="hero-note">Products looked at on this shelf</p>
        </article>
        <article className={hot ? 'hero dwell hot' : 'hero dwell'}>
          <p className="hero-label">{between ? 'Between products' : 'Dwelling on one zone'}</p>
          <p className="hero-num timer" data-testid="dwell-timer">
            {formatTimer(between ? 0 : snap.dwellMs)}
          </p>
          <p className="hero-note">{shown ? shown.name : 'Timer resets when the look moves'}</p>
        </article>
      </div>

      <div className="fixture" aria-label="Shelf">
        {[['Drinks', 'Drinks'], ['Snacks', 'Snacks'], ['Sauces', 'Sauces and other']].map(([category, label]) => (
        <section key={category} className="category-block">
        <h2 className="category">{label}</h2>
        <div className="shelf">
          {week.products.filter((product) => product.category === category).map((product) => {
            const on = product.id === snap.activeId
            const flash = snap.flash?.productId === product.id ? snap.flash.kind : null
            const fill = on ? Math.min(100, (snap.dwellMs / 8000) * 100) : 0
            return (
              <div key={product.id} className={on ? 'pack on' : flash ? `pack ${flash}` : 'pack'}>
                <div className="pack-face">
                  <i style={{ background: product.color }} />
                  <span>{product.brand}</span>
                  <strong title={product.name}>{product.short}</strong>
                  <em>£{product.price.toFixed(2)}</em>
                </div>
                <div className="meter">
                  <span style={{ width: `${fill}%` }} />
                </div>
                <small>{product.position}</small>
              </div>
            )
          })}
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
                    <strong>{product?.name || entry.productId}</strong>
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

function labelFor(kind) {
  if (kind === 'miss') return 'Near-miss'
  if (kind === 'buy') return 'Purchase'
  if (kind === 'slide') return 'Slide-off'
  return 'Glance'
}
