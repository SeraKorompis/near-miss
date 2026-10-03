/**
 * Near-miss model for one fixture.
 *
 * A near-miss is a look of at least 3 seconds that does not become a purchase.
 * Leakage is what those looks were worth if a share of them can be won back.
 * The action is the next retail decision: reprice, clarify the pack, move it,
 * promote it, give it another facing, or leave it alone.
 *
 * Product names match the filmed shelf. Volumes are a synthetic week, not a till extract.
 * The live feed matches on the product name the vision model returns.
 */

export const ASSUMPTIONS = {
  closeBack: 0.42,
  repriceYield: 0.55,
  clarifyYield: 0.4,
  repositionTake: 0.02,
  promoteFill: 0.25,
  expandLift: 0.12,
  nearMissMs: 3000,
  glanceMs: 400,
  riskCenterSec: 3.2,
  riskSlope: 0.85,
}

function sku(partial) {
  return {
    position: 'Eye level',
    glances: 480,
    avgDwellMs: 3100,
    nearMisses: 64,
    purchases: 155,
    revisits: 1.3,
    peerMedian: partial.category === 'Sauces' ? 4.2 : partial.category === 'Snacks' ? 1.9 : 1.85,
    ...partial,
  }
}

export const products = [
  sku({ id: 'fizz-lemon', short: 'Lemon', name: 'Fermented Fizz Lemon Lemonade', brand: 'Fermented Fizz', price: 2.4, category: 'Drinks', color: '#e3d15a' }),
  sku({ id: 'fizz-orange', short: 'Orange', name: 'Fermented Fizz Orange', brand: 'Fermented Fizz', price: 2.4, category: 'Drinks', color: '#e38b2c' }),
  sku({ id: 'fizz-pink', short: 'Pink berry', name: 'Fermented Fizz Pink Berry', brand: 'Fermented Fizz', price: 2.4, category: 'Drinks', color: '#e36a8a' }),
  sku({ id: 'navas-tonic', short: 'Tonic', name: 'Navas Original Tonic Water', brand: 'Navas', price: 1.8, category: 'Drinks', color: '#1f6f8a' }),
  sku({
    id: 'navas-ginger',
    short: 'Ginger beer',
    name: 'Navas Fiery Ginger Beer',
    brand: 'Navas',
    price: 1.9,
    category: 'Drinks',
    color: '#d06a1f',
    glances: 280,
    avgDwellMs: 3400,
    nearMisses: 28,
    purchases: 120,
    revisits: 1.2,
  }),
  sku({ id: 'lowrise-pale', short: 'Hazy pale', name: 'Lowrise Hazy Pale', brand: 'Lowrise', price: 2.8, category: 'Drinks', color: '#c4a15a' }),
  sku({
    id: 'lowrise-lager',
    short: 'Lager',
    name: 'Lowrise Lager',
    brand: 'Lowrise',
    price: 2.6,
    category: 'Drinks',
    color: '#e2b84a',
    glances: 700,
    avgDwellMs: 4200,
    nearMisses: 60,
    purchases: 360,
    revisits: 1.5,
  }),
  sku({
    id: 'dash-pink',
    short: 'Pink Lady',
    name: 'Dash Pink Lady Apple Sparkling Water',
    brand: 'Dash',
    price: 2.5,
    suggestedPrice: 1.8,
    category: 'Drinks',
    color: '#e07a9a',
    peerMedian: 1.6,
    glances: 820,
    avgDwellMs: 6400,
    nearMisses: 210,
    purchases: 88,
    revisits: 1.3,
  }),
  sku({ id: 'dash-citrus', short: 'Citrus', name: 'Dash Sparkling Water', brand: 'Dash', price: 1.6, category: 'Drinks', color: '#b6d14a' }),
  sku({ id: 'coastal', short: 'Spritz', name: 'Coastal Spritz', brand: 'Pentire', price: 3.2, category: 'Drinks', color: '#1f8a78' }),
  sku({ id: 'oom', short: 'Balance', name: 'OOM Balance', brand: 'OOM', price: 2.4, category: 'Drinks', color: '#6a8f4a' }),
  sku({ id: 'charitea', short: 'Mate', name: 'ChariTea Mate Sparkling', brand: 'ChariTea', price: 2.2, category: 'Drinks', color: '#c45a2a' }),
  sku({ id: 'epic-plant', short: 'Plant power', name: 'Epic Plant Power Toastin’ Marshmallows', brand: 'Epic', price: 3.5, category: 'Snacks', color: '#f2efe6' }),
  sku({ id: 'epic-giant', short: 'Giant', name: 'Epic Giant Toastin’ Marshmallows', brand: 'Epic', price: 4, category: 'Snacks', color: '#efe4d2' }),
  sku({ id: 'kook', short: 'Pouches', name: 'KOOK snack pouches', brand: 'KOOK', price: 2, category: 'Snacks', color: '#e24b3a' }),
  sku({ id: 'brain-bar', short: 'Brain Bar', name: 'Brain Bar', brand: 'Brain Bar', price: 2.2, category: 'Snacks', color: '#5a3a8a' }),
  sku({ id: 'pball-original', short: 'Original', name: 'The Protein Ball Co. Original', brand: 'Protein Ball Co.', price: 1.9, category: 'Snacks', color: '#c4a574' }),
  sku({ id: 'pball-caramel', short: 'Salted caramel', name: 'The Protein Ball Co. Salted Caramel', brand: 'Protein Ball Co.', price: 1.9, category: 'Snacks', color: '#b88858' }),
  sku({ id: 'pball-peanut', short: 'Peanut butter', name: 'The Protein Ball Co. Peanut Butter', brand: 'Protein Ball Co.', price: 1.9, category: 'Snacks', color: '#a87440' }),
  sku({
    id: 'thins',
    short: 'Thins',
    name: 'Well & Truly Thins, Rich Cheddar & Gouda with a Hint of Jalapeño',
    brand: 'Well & Truly',
    price: 2.2,
    category: 'Snacks',
    color: '#f0c14a',
    glances: 510,
    avgDwellMs: 8100,
    nearMisses: 188,
    purchases: 46,
    revisits: 3.2,
  }),
  sku({ id: 'crunch-cheesy', short: 'Really cheesy', name: 'Well & Truly Crunchies, Really Cheesy', brand: 'Well & Truly', price: 1.8, category: 'Snacks', color: '#e2b423' }),
  sku({ id: 'crunch-cider', short: 'Salt & cider', name: 'Well & Truly Crunchies, Salt & Cider Vinegar', brand: 'Well & Truly', price: 1.8, category: 'Snacks', color: '#d4b04a' }),
  sku({ id: 'crunch-bacon', short: 'Smokey bacon', name: 'Well & Truly Crunchies, Smokey Bacon', brand: 'Well & Truly', price: 1.8, category: 'Snacks', color: '#c4843a' }),
  sku({
    id: 'crunch-paprika',
    short: 'Paprika',
    name: 'Well & Truly Crunchies, Smokey Paprika',
    brand: 'Well & Truly',
    price: 1.8,
    category: 'Snacks',
    position: 'Partly hidden',
    color: '#c4481d',
    glances: 1100,
    avgDwellMs: 700,
    nearMisses: 22,
    purchases: 40,
    revisits: 1.1,
  }),
  sku({ id: 'fudge', short: 'Fudge', name: 'Well & Truly Fudge & Brownie Oat Milk Chocolate', brand: 'Well & Truly', price: 2.5, category: 'Snacks', color: '#6b3a2a' }),
  sku({ id: 'puffs', short: 'Puffs', name: 'All That Matters Superfood Puffs', brand: 'All That Matters', price: 2.4, category: 'Snacks', color: '#3a8f6a' }),
  sku({ id: 'crisps-cider', short: 'Salt & cider', name: 'Simply Roasted Crisps, Sea Salt & Cider Vinegar', brand: 'Simply Roasted', price: 1.5, category: 'Snacks', color: '#d4a017' }),
  sku({ id: 'crisps-cheddar', short: 'Cheddar', name: 'Simply Roasted Crisps, Mature Cheddar & Red Onion', brand: 'Simply Roasted', price: 1.5, category: 'Snacks', color: '#c4922a' }),
  sku({ id: 'crisps-salt', short: 'Sea salt', name: 'Simply Roasted Crisps, Sea Salt', brand: 'Simply Roasted', price: 1.5, category: 'Snacks', color: '#e0c878' }),
  sku({ id: 'buffalo', short: 'Buffalo', name: 'Dr. Will’s Buffalo Sauce', brand: 'Dr. Will’s', price: 4.2, category: 'Sauces', color: '#c43a2a' }),
  sku({ id: 'mayo', short: 'Mayo', name: 'Dr. Will’s All Natural Avocado Oil Mayo', brand: 'Dr. Will’s', price: 4.5, category: 'Sauces', color: '#7a9a4a' }),
  sku({
    id: 'corned',
    short: 'Corned beef',
    name: 'Helen Browning’s Organic Corned Beef',
    brand: 'Helen Browning’s',
    price: 5.4,
    category: 'Sauces',
    color: '#8a4b32',
    glances: 140,
    avgDwellMs: 1500,
    nearMisses: 16,
    purchases: 12,
    revisits: 1,
  }),
]

export const shelf = products.map((p) => p.id)

export const weekShape = [
  { day: 'Mon', share: 0.13 },
  { day: 'Tue', share: 0.14 },
  { day: 'Wed', share: 0.12 },
  { day: 'Thu', share: 0.16 },
  { day: 'Fri', share: 0.19 },
  { day: 'Sat', share: 0.17 },
  { day: 'Sun', share: 0.09 },
]

export const sessions = [
  {
    when: 'Sat 10:06',
    products: 6,
    glances: 7,
    dwell: '8.6s Well & Truly Thins',
    result: 'Near-miss',
    note: 'Put the thins back, then bought Lowrise Lager.',
  },
  {
    when: 'Sat 10:18',
    products: 4,
    glances: 3,
    dwell: '4.3s Navas ginger beer',
    result: 'Purchase',
    note: 'Slid off the paprika crunchies before it became a look.',
  },
  {
    when: 'Sat 10:41',
    products: 3,
    glances: 4,
    dwell: '6.8s Dash Pink Lady',
    result: 'Near-miss',
    note: 'Held the can, checked the price, walked.',
  },
  {
    when: 'Sat 11:02',
    products: 5,
    glances: 6,
    dwell: '9.1s Well & Truly Thins',
    result: 'Near-miss',
    note: 'Third look at the pack. Still no pickup.',
  },
  {
    when: 'Sat 11:27',
    products: 2,
    glances: 2,
    dwell: '4.4s Lowrise Lager',
    result: 'Purchase',
    note: 'Straight to the product that already converts.',
  },
  {
    when: 'Sat 11:49',
    products: 5,
    glances: 5,
    dwell: '1.8s superfood puffs',
    result: 'Pass',
    note: 'Browsed the snack end and left with nothing.',
  },
  {
    when: 'Sat 12:16',
    products: 4,
    glances: 5,
    dwell: '7.4s Dash Pink Lady',
    result: 'Near-miss',
    note: 'Came back to Pink Lady after the tonic. Bought the tonic.',
  },
  {
    when: 'Sat 12:33',
    products: 3,
    glances: 3,
    dwell: '3.9s Fermented Fizz lemon',
    result: 'Purchase',
    note: 'Healthy dwell, healthy close. Leave it.',
  },
]

export const shoppers = [
  {
    id: 'A',
    events: [
      { productId: 'dash-pink', ms: 1100 },
      { productId: 'lowrise-lager', ms: 1700 },
      { productId: 'dash-pink', ms: 8200, outcome: 'leave' },
      { productId: 'crunch-paprika', ms: 520 },
      { productId: 'thins', ms: 8600, outcome: 'leave' },
      { productId: 'lowrise-lager', ms: 4700, outcome: 'purchase' },
    ],
  },
  {
    id: 'B',
    events: [
      { productId: 'corned', ms: 480 },
      { productId: 'puffs', ms: 1900 },
      { productId: 'crunch-paprika', ms: 360 },
      { productId: 'navas-ginger', ms: 4300, outcome: 'purchase' },
    ],
  },
  {
    id: 'C',
    events: [
      { productId: 'lowrise-lager', ms: 2400 },
      { productId: 'dash-pink', ms: 6900, outcome: 'leave' },
      { productId: 'fizz-lemon', ms: 4000, outcome: 'purchase' },
    ],
  },
]

const PERIOD = { today: 1 / 6, week: 1, month: 4 }

export function money(value, pence = false) {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    minimumFractionDigits: pence ? 2 : 0,
    maximumFractionDigits: pence ? 2 : 0,
  }).format(value)
}

export function pct(value) {
  return `${Math.round(value * 100)}%`
}

export function secs(ms) {
  return `${(ms / 1000).toFixed(1)}s`
}

export function formatTimer(ms) {
  const tenths = Math.max(0, Math.floor(ms / 100))
  const minutes = Math.floor(tenths / 600)
  const seconds = Math.floor(tenths / 10) % 60
  const tenth = tenths % 10
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${tenth}`
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2) return sorted[mid]
  return (sorted[mid - 1] + sorted[mid]) / 2
}

function confidence(glances) {
  if (glances >= 500) return 'high'
  if (glances >= 300) return 'medium'
  return 'low'
}

function recoveryOf(action, p) {
  const { closeBack, repriceYield, clarifyYield, repositionTake, promoteFill, expandLift } = ASSUMPTIONS
  switch (action) {
    case 'reprice':
      return p.nearMisses * p.price * closeBack * repriceYield
    case 'clarify':
      return p.nearMisses * p.price * closeBack * clarifyYield
    case 'reposition':
      return p.glances * p.price * repositionTake
    case 'promote':
      return Math.max(0, p.median - p.glances) * p.conversion * p.price * promoteFill
    case 'expand':
      return p.purchases * p.price * expandLift
    default:
      return 0
  }
}

function decide(p) {
  const { conversion, avgDwellMs, revisits, price, peerMedian, glances, median: mid } = p
  let action = 'hold'
  if (conversion >= 0.45 && avgDwellMs >= 3500) action = 'expand'
  else if (conversion >= 0.38 && glances < mid * 0.7) action = 'promote'
  else if (avgDwellMs < 1200 && glances > mid) action = 'reposition'
  else if (avgDwellMs >= 6000 && revisits >= 2.5 && conversion < 0.2) action = 'clarify'
  else if (avgDwellMs >= 4000 && conversion < 0.2 && price > peerMedian + 0.3) action = 'reprice'
  else if (glances < mid * 0.4 && conversion < 0.15) action = 'review'

  const copy = {
    reprice: {
      title: 'Test a lower price',
      next: `Move ${p.name} from ${money(price, true)} to a ${money(p.suggestedPrice ?? peerMedian, true)} test for one week.`,
      why: `${p.name} holds a look for ${secs(avgDwellMs)} — long enough to decide — and only ${pct(conversion)} of glances become a sale. ${p.nearMisses} looks a week pass 3 seconds and still walk. It sits ${money(price - peerMedian, true)} above the other ${p.category.toLowerCase()} on this fixture. Position is not the problem. Price is.`,
      math: 'near-misses × price × 0.42 close-back × 0.55 price-test yield',
    },
    clarify: {
      title: 'Simplify the pack',
      next: `Rewrite the ${p.name} front so one claim is readable at arm's length.`,
      why: `Long dwell (${secs(avgDwellMs)}) and repeat looks (${revisits.toFixed(1)} per shopper who stops). People are trying to decide and failing. Conversion is ${pct(conversion)}. A price cut is the wrong first move — the second and third look say the front of pack is the block.`,
      math: 'near-misses × price × 0.42 close-back × 0.40 pack-fix yield',
    },
    reposition: {
      title: 'Move it up the fixture',
      next: `Bring ${p.name} out of ${p.position.toLowerCase()} for a week, next to products that already hold a look.`,
      why: `Lots of glances, shortest look (${secs(avgDwellMs)}). It wins a flick of the eye and loses the next second. Shoppers never reach a price decision, so a discount will not show up in the till.`,
      math: 'glances × price × 0.02 looks we expect to hold after the move',
    },
    promote: {
      title: 'Put it where people stop',
      next: `Give ${p.name} a shelf talker or the end of the fixture. Do not change the price.`,
      why: `${pct(conversion)} of glances already convert, above the aisle, but it is seen far less than the products beside it. The product works. Discovery is the constraint.`,
      math: 'missing glances vs the fixture median × conversion × price × 0.25 of that gap',
    },
    expand: {
      title: 'Add a facing',
      next: `Give ${p.name} a second facing. Leave the price where it is.`,
      why: `Best converter on the fixture at ${pct(conversion)}, with a healthy ${secs(avgDwellMs)} dwell. This is the product the shelf should make more room for. Take the facing from a product that is not earning it.`,
      math: 'current weekly sales × price × 12% lift from one extra facing',
    },
    review: {
      title: 'Free the facing',
      next: `Stop defending ${p.name}. Confirm one more week, then give the slot to a product that already converts.`,
      why: `Only ${glances} glances a week, and ${pct(conversion)} conversion. The sample is small, so this is a watch-out rather than a delist order. It earns about ${money(p.purchases * price)} a week from a full facing.`,
      math: 'No recovered revenue counted — the value is the facing, already counted if you expand a winner.',
    },
    hold: {
      title: 'Leave it',
      next: `No move on ${p.name} this week.`,
      why: `Dwell and conversion sit with the healthy part of the fixture. Changing it would spend a test on a product that is already doing its job.`,
      math: 'No recovered revenue — acting here does not pay.',
    },
  }[action]

  return {
    action,
    ...copy,
    recovery: recoveryOf(action, p),
    confidence: confidence(p.weeklyGlances),
  }
}

function decorate(raw, mid) {
  const conversion = raw.purchases / raw.glances
  const base = {
    ...raw,
    conversion,
    walkAway: 1 - conversion,
    nearMissRate: raw.nearMisses / raw.glances,
    median: mid,
    weeklyGlances: raw.glances,
  }
  return { ...base, ...decide(base) }
}

function applyPeriod(scored, period) {
  const scale = PERIOD[period] ?? 1
  return scored.map((p) => ({
    ...p,
    glances: Math.round(p.glances * scale),
    nearMisses: Math.round(p.nearMisses * scale),
    purchases: Math.round(p.purchases * scale),
    leakage: p.nearMisses * p.price * ASSUMPTIONS.closeBack * scale,
    recovery: p.recovery * scale,
    attentionMs: p.glances * p.avgDwellMs * scale,
  }))
}

export function analyse(period = 'week') {
  const mid = median(products.map((p) => p.glances))
  const scored = applyPeriod(products.map((p) => decorate(p, mid)), period)
  const byId = Object.fromEntries(scored.map((p) => [p.id, p]))
  const queue = scored
    .filter((p) => p.action !== 'hold')
    .sort((a, b) => b.recovery - a.recovery || b.leakage - a.leakage)
  const leakage = scored.reduce((sum, p) => sum + p.leakage, 0)
  const nearMisses = scored.reduce((sum, p) => sum + p.nearMisses, 0)
  const glances = scored.reduce((sum, p) => sum + p.glances, 0)
  const purchases = scored.reduce((sum, p) => sum + p.purchases, 0)
  const attentionMs = scored.reduce((sum, p) => sum + p.attentionMs, 0)
  const recoverable = queue.filter((p) => p.recovery > 0).slice(0, 3)
  return {
    period,
    products: shelf.map((id) => byId[id]),
    byId,
    queue,
    holds: scored.filter((p) => p.action === 'hold'),
    leakage,
    nearMisses,
    glances,
    purchases,
    attentionMs,
    conversion: purchases / glances,
    nearMissRate: nearMisses / glances,
    recoverable,
    recovered: recoverable.reduce((sum, p) => sum + p.recovery, 0),
    medianGlances: mid * (PERIOD[period] ?? 1),
  }
}

export function liveRisk(product, dwellMs) {
  const sec = dwellMs / 1000
  const hesitation = 1 / (1 + Math.exp(-ASSUMPTIONS.riskSlope * (sec - ASSUMPTIONS.riskCenterSec)))
  const risk = 0.08 + (product.walkAway - 0.08) * hesitation
  return Math.min(0.96, Math.max(0.05, risk))
}

function norm(value) {
  return String(value).trim().toLowerCase().replace(/[’‘ʼ]/g, "'")
}

export function resolveProduct(token) {
  if (token == null || token === '') return null
  const q = norm(token)
  return products.find((p) => norm(p.id) === q || norm(p.name) === q || norm(p.short) === q) || null
}

export function contrastProduct(activeId, list) {
  const others = list.filter((p) => p.id !== activeId)
  return [...others].sort((a, b) => b.conversion - a.conversion)[0] || null
}
