import { useMemo, useState } from 'react'
import { analyse, money, pct, secs, sessions, weekShape } from './model'

const ACTIONS = {
  reprice: 'Reprice',
  clarify: 'Clarify pack',
  reposition: 'Move up',
  promote: 'Promote',
  expand: 'Add facing',
  review: 'Free facing',
  hold: 'Leave it',
}

const PERIODS = [
  { id: 'today', label: 'Today', word: 'today' },
  { id: 'week', label: 'This week', word: 'this week' },
  { id: 'month', label: 'This month', word: 'this month' },
]

export function History() {
  const [period, setPeriod] = useState('week')
  const report = useMemo(() => analyse(period), [period])
  const word = PERIODS.find((item) => item.id === period).word
  const lead = report.queue[0]
  const maxLeak = Math.max(...report.products.map((p) => p.leakage))

  return (
    <section className="history">
      <div className="history-head">
        <div>
          <p className="kicker">What the buyer should do next</p>
          <h2>
            This fixture is leaking {money(report.leakage)} {word}.
          </h2>
          <p className="lede">
            {money(report.recovered)} comes back if you take the first three moves. The ranking is predicted recovered revenue, not raw attention. A product people stare at and still buy is not a problem. Figures are a synthetic week for a fictional fixture — stable rates, simulated till — and the rules are at the bottom of this page.
          </p>
        </div>
        <div className="periods" role="group" aria-label="Time range">
          {PERIODS.map((item) => (
            <button key={item.id} type="button" aria-pressed={period === item.id} onClick={() => setPeriod(item.id)}>
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <p className="next-call" data-testid="next-move">
        <span>Next</span>
        {lead.title} — {lead.name}
      </p>

      <dl className="kpis">
        <div>
          <dt>Glances</dt>
          <dd data-testid="history-glances">{report.glances.toLocaleString('en-GB')}</dd>
        </div>
        <div>
          <dt>Products</dt>
          <dd>8</dd>
        </div>
        <div>
          <dt>Attention</dt>
          <dd>{(report.attentionMs / 3600000).toFixed(1)}h</dd>
        </div>
        <div>
          <dt>Near-misses</dt>
          <dd>{report.nearMisses.toLocaleString('en-GB')}</dd>
        </div>
        <div>
          <dt>Near-miss rate</dt>
          <dd>{pct(report.nearMissRate)}</dd>
        </div>
        <div>
          <dt>Conversion</dt>
          <dd>{pct(report.conversion)}</dd>
        </div>
      </dl>

      <ol className="queue">
        {report.queue.map((product, index) => (
          <li key={product.id} className={product.action}>
            <p className="queue-index">{String(index + 1).padStart(2, '0')}</p>
            <div>
              <p className="queue-action">{product.title}</p>
              <h3>
                {product.name}
                <span>{money(product.price, true)}</span>
              </h3>
              <p>{product.why}</p>
              <p className="math">{product.math}</p>
            </div>
            <div className="queue-value">
              <strong>{product.recovery > 0 ? money(product.recovery) : '—'}</strong>
              <span>{product.recovery > 0 ? `predicted back ${word}` : 'facing, not cash'}</span>
              <em>
                {product.confidence} confidence · {product.weeklyGlances.toLocaleString('en-GB')} weekly glances
              </em>
            </div>
          </li>
        ))}
      </ol>

      <p className="holds">
        Leave alone {word}: {report.holds.length} products already convert when they are seen.
      </p>

      <div className="stack">
        <article className="panel">
          <p className="kicker">Where the money walks away</p>
          <h3>Leakage by product</h3>
          <ul className="bars">
            {[...report.products]
              .sort((a, b) => b.leakage - a.leakage)
              .map((product) => (
                <li key={product.id}>
                  <span className="bar-name">{product.name}</span>
                  <span className="bar-track">
                    <span className={product.action} style={{ width: `${(product.leakage / maxLeak) * 100}%` }} />
                  </span>
                  <span className="bar-value">{money(product.leakage)}</span>
                </li>
              ))}
          </ul>
        </article>

        <article className="panel">
          <p className="kicker">Attention against the till</p>
          <h3>Dwell versus conversion</h3>
          <p className="fine">Crosshairs at 3 seconds and 30% conversion. Bottom right is a near-miss: they studied it and did not buy. Bottom left was seen and not studied. Above the line, it sells.</p>
          <Scatter products={report.products} />
        </article>
      </div>

      <div className="stack">
        <article className="panel">
          <p className="kicker">Shape of the week</p>
          <h3>Near-misses by day</h3>
          <div className="days" aria-hidden="true">
            {weekShape.map((day) => (
              <div key={day.day} className="day">
                <span style={{ height: `${Math.round((day.share / 0.19) * 112)}px` }} />
                <small>{day.day}</small>
              </div>
            ))}
          </div>
          <p className="fine">Friday is the heavy day. Today and this month scale the week’s volume — they do not invent a new pattern. Rates, and therefore the decision, stay put.</p>
        </article>
      </div>

      <article className="panel">
        <p className="kicker">All products</p>
        <h3>The fixture, in full</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Price</th>
                <th>Glances</th>
                <th>Avg dwell</th>
                <th>Near-misses</th>
                <th>Conversion</th>
                <th>Leakage</th>
                <th>Next move</th>
              </tr>
            </thead>
            <tbody>
              {[...report.products]
                .sort((a, b) => b.leakage - a.leakage)
                .map((product) => (
                  <tr key={product.id}>
                    <td>
                      <strong>{product.name}</strong>
                      <small>{product.brand} · {product.position}</small>
                    </td>
                    <td>{money(product.price, true)}</td>
                    <td>{product.glances.toLocaleString('en-GB')}</td>
                    <td>{secs(product.avgDwellMs)}</td>
                    <td>{product.nearMisses.toLocaleString('en-GB')}</td>
                    <td>{pct(product.conversion)}</td>
                    <td>{money(product.leakage)}</td>
                    <td className={product.action}>{ACTIONS[product.action]}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel">
        <p className="kicker">Session sample</p>
        <h3>Scripted trips from the synthetic week</h3>
        <p className="fine">A sample, not the ledger. Totals above are the full week, so they will not match the sum of these rows.</p>
        <div className="table-wrap">
          <table className="sessions">
            <thead>
              <tr>
                <th>When</th>
                <th>Products</th>
                <th>Glances</th>
                <th>Longest look</th>
                <th>Result</th>
                <th>What happened</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.when}>
                  <td>{session.when}</td>
                  <td>{session.products}</td>
                  <td>{session.glances}</td>
                  <td>{session.dwell}</td>
                  <td className={session.result === 'Near-miss' ? 'miss' : session.result === 'Purchase' ? 'buy' : ''}>{session.result}</td>
                  <td>{session.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel assumptions">
        <p className="kicker">How the number is made</p>
        <h3>Assumptions a buyer can argue with</h3>
        <ul>
          <li>A glance is a look of at least 0.4 seconds. A near-miss is a look of at least 3 seconds with no purchase.</li>
          <li>Leakage = near-misses × price × 0.42. The 0.42 is the share we assume we can win back if we fix the friction we named. It is a planning factor, not a measured close rate.</li>
          <li>Price-test yield 0.55 of leakage. Pack-fix yield 0.40. A move up the shelf holds 2% of glances that currently slide off. A promotion fills 25% of the glance gap to the fixture median. An extra facing lifts sales 12%.</li>
          <li>Live risk starts near 8% and rises with dwell toward that product’s historical walk-away rate: 0.08 + (1 − conversion − 0.08) × sigmoid(0.85 × (seconds − 3.2)).</li>
          <li>Confidence uses the weekly sample, so switching to today does not pretend the evidence got thinner. Under 300 weekly glances stays a low-confidence watch-out.</li>
          <li>History volumes are synthetic. Product names are the filmed shelf. Head direction is a proxy for gaze. There is no shopper identity — the live feed sends a product name only. The till side is a simulated purchase log until a real one is connected.</li>
        </ul>
      </article>
    </section>
  )
}

function Scatter({ products }) {
  const width = 960
  const height = 380
  const pad = { l: 48, r: 88, t: 20, b: 32 }
  const xMax = 10
  const yMax = 0.6
  const xOf = (ms) => pad.l + (ms / 1000 / xMax) * (width - pad.l - pad.r)
  const yOf = (conv) => pad.t + (1 - conv / yMax) * (height - pad.t - pad.b)
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Scatter of average dwell against conversion">
      <line x1={pad.l} y1={yOf(0.3)} x2={width - pad.r} y2={yOf(0.3)} className="grid" />
      <line x1={xOf(3000)} y1={pad.t} x2={xOf(3000)} y2={height - pad.b} className="grid" />
      {products.map((product) => {
        const x = xOf(product.avgDwellMs)
        const y = yOf(product.conversion)
        return (
          <g key={product.id} className={product.action}>
            <circle cx={x} cy={y} r={product.action === 'hold' ? 4 : 7} />
            {product.action !== 'hold' && <text x={x + 10} y={y + 4}>{product.short}</text>}
          </g>
        )
      })}
      <text x={(pad.l + width - pad.r) / 2} y={height - 6} textAnchor="middle" className="axis">Average dwell →</text>
      <text x={14} y={(pad.t + height - pad.b) / 2} transform={`rotate(-90 14 ${(pad.t + height - pad.b) / 2})`} textAnchor="middle" className="axis">Conversion →</text>
    </svg>
  )
}
