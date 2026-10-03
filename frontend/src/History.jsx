import results from '../../output/results.json'
import recommendations from '../../output/recommendations.json'
import { pct } from './model'

const OUTCOME = {
  near_miss_put_back: 'Picked up, put back',
  near_miss_looked: 'Looked, never touched',
  purchase: 'Bought',
  glance: 'Glance',
}

const PRIORITY = { high: 'High', medium: 'Medium', low: 'Low' }

export function History() {
  const { summary, products, moments } = results
  const nearMissRate = summary.interested_pairs ? summary.near_misses / summary.interested_pairs : 0
  const maxNear = Math.max(1, ...products.map((product) => product.near_misses))
  const lead = products.find((product) => recommendations[product.product_id]) || products[0]
  const leadRec = lead ? recommendations[lead.product_id] : null

  return (
    <section className="history">
      <div className="history-head">
        <div>
          <p className="kicker">What the buyer should do next</p>
          <h2>
            {summary.near_misses} near-miss{summary.near_misses === 1 ? '' : 'es'} across the demo clips.
          </h2>
          <p className="lede">
            Taken from the three tripod videos and the simulated till. A near-miss is a pickup that goes back, or a look of at least {summary.dwell_threshold_s}s with no touch and no purchase. Brief glances are not counted as interest.
          </p>
        </div>
      </div>

      {lead && leadRec && (
        <p className="next-call" data-testid="next-move">
          <span>Next</span>
          {leadRec.action} — {humanize(lead.product_id)}
        </p>
      )}

      <dl className="kpis">
        <div>
          <dt>Shoppers</dt>
          <dd>{summary.shoppers}</dd>
        </div>
        <div>
          <dt>Interested</dt>
          <dd>{summary.interested_pairs}</dd>
        </div>
        <div>
          <dt>Purchases</dt>
          <dd>{summary.purchases}</dd>
        </div>
        <div>
          <dt>Near-misses</dt>
          <dd>{summary.near_misses}</dd>
        </div>
        <div>
          <dt>Near-miss rate</dt>
          <dd>{pct(nearMissRate)}</dd>
        </div>
        <div>
          <dt>Conversion</dt>
          <dd>{pct(summary.conversion_rate)}</dd>
        </div>
      </dl>

      <ol className="queue">
        {products.map((product, index) => {
          const rec = recommendations[product.product_id] || {}
          const priority = rec.priority || 'low'
          return (
            <li key={product.product_id} className={`priority-${priority}`}>
              <p className="queue-index">{String(index + 1).padStart(2, '0')}</p>
              <div>
                <p className="queue-action">{PRIORITY[priority] || priority}</p>
                <h3>{humanize(product.product_id)}</h3>
                <p>{rec.diagnosis}</p>
                <p className="math">{rec.action}</p>
              </div>
              <div className="queue-value">
                <strong>{product.near_misses}</strong>
                <span>{product.near_misses === 1 ? 'near-miss' : 'near-misses'}</span>
                <em>
                  {product.purchases} bought · {product.avg_dwell_s.toFixed(1)}s avg attention
                </em>
              </div>
            </li>
          )
        })}
      </ol>

      <div className="stack">
        <article className="panel">
          <p className="kicker">Where interest walks away</p>
          <h3>Near-misses by product</h3>
          <ul className="bars">
            {products.map((product) => (
              <li key={product.product_id}>
                <span className="bar-name">{humanize(product.product_id)}</span>
                <span className="bar-track">
                  <span
                    className={recommendations[product.product_id]?.priority === 'low' ? 'promote' : ''}
                    style={{ width: `${(product.near_misses / maxNear) * 100}%` }}
                  />
                </span>
                <span className="bar-value">{product.near_misses}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <p className="kicker">Interested shoppers</p>
          <h3>Bought against walked away</h3>
          <ul className="bars">
            {products.map((product) => {
              const total = product.purchases + product.near_misses
              return (
                <li key={product.product_id}>
                  <span className="bar-name">{humanize(product.product_id)}</span>
                  <span className="bar-track">
                    <span className="promote" style={{ width: total ? `${(product.purchases / total) * 100}%` : '0%' }} />
                  </span>
                  <span className="bar-value">{product.purchases}/{total || 0}</span>
                </li>
              )
            })}
          </ul>
          <p className="fine">The bar is the share who bought. The fraction is purchases over interested shoppers.</p>
        </article>
      </div>

      <article className="panel">
        <p className="kicker">All products</p>
        <h3>The clips, in full</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Noticed</th>
                <th>Interested</th>
                <th>Avg dwell</th>
                <th>Near-misses</th>
                <th>Bought</th>
                <th>Conversion</th>
                <th>Next move</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => {
                const rec = recommendations[product.product_id]
                const priority = rec?.priority || 'low'
                return (
                  <tr key={product.product_id}>
                    <td>
                      <strong>{humanize(product.product_id)}</strong>
                      <small>{product.near_miss_put_back} put back · {product.near_miss_looked} looked only</small>
                    </td>
                    <td>{product.shoppers_noticed}</td>
                    <td>{product.shoppers_interested}</td>
                    <td>{product.avg_dwell_s.toFixed(1)}s</td>
                    <td className="miss">{product.near_misses}</td>
                    <td className="buy">{product.purchases}</td>
                    <td>{pct(product.conversion_rate)}</td>
                    <td className={priority === 'low' ? 'hold' : 'reprice'}>{rec?.action || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel">
        <p className="kicker">What the camera saw</p>
        <h3>Moments from the demo clips</h3>
        <div className="table-wrap">
          <table className="sessions">
            <thead>
              <tr>
                <th>Clip</th>
                <th>Product</th>
                <th>Dwell</th>
                <th>From</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {moments.map((moment) => (
                <tr key={`${moment.shopper}-${moment.product_id}-${moment.start_s}`}>
                  <td>{moment.video}</td>
                  <td>{humanize(moment.product_id)}</td>
                  <td>{moment.dwell_s.toFixed(1)}s</td>
                  <td>{moment.start_s.toFixed(1)}s</td>
                  <td className={moment.outcome.startsWith('near_miss') ? 'miss' : moment.outcome === 'purchase' ? 'buy' : ''}>
                    {OUTCOME[moment.outcome] || moment.outcome}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel assumptions">
        <p className="kicker">How a near-miss is called</p>
        <h3>From the vision pipeline</h3>
        <ul>
          <li>Interest is a look of at least {summary.dwell_threshold_s} seconds, or a touch. Anything shorter is a glance and is left out of the rate.</li>
          <li>Put back: they touched it and the till log does not show a purchase. Looked: they stayed for {summary.dwell_threshold_s}s or more, never touched, and did not buy.</li>
          <li>Purchases come from <code>analysis/till_log.csv</code>, a simulated till for these three clips.</li>
          <li>The next move is the recommendation written to <code>output/recommendations.json</code>. If Ollama is not running, that file falls back to the rules in <code>analysis/recommend.py</code>.</li>
        </ul>
      </article>
    </section>
  )
}

function humanize(id) {
  const text = String(id).replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Unknown product'
}
