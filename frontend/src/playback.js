/**
 * Plays scripted shoppers, or accepts a live gaze stream.
 *
 * Live video swaps in without touching the dashboard. From the vision
 * pipeline (or the browser console while a clip plays):
 *
 *   NearMiss.gaze('Dash Pink Lady Apple Sparkling Water')  // product name, or null
 *   NearMiss.purchase('Dash Pink Lady Apple Sparkling Water')
 *   NearMiss.reset()
 *
 * Or a WebSocket via ?feed=ws://localhost:8765 sending
 *   { "type": "gaze", "name": "crisps_packs", "dwellMs": 1400, "touch": false }
 *   { "type": "purchase", "name": "Lowrise Lager" }
 *   { "type": "reset" }
 *
 * When dwellMs is present it is the duration the camera measured, and the
 * dashboard shows that number instead of timing the look itself. A name that
 * is not on the dummy shelf is still shown.
 */

import { ASSUMPTIONS, analyse, resolveProduct, shoppers } from './model.js'

function asId(token) {
  if (token == null || token === '') return null
  return resolveProduct(token)?.id || String(token)
}

const GAP_MS = 680
const BETWEEN_MS = 1200

export function idle() {
  return {
    shopperIndex: 0,
    eventIndex: 0,
    phase: 'gap',
    elapsed: 0,
    glances: 0,
    demoGlances: 0,
    seen: [],
    activeId: null,
    dwellMs: 0,
    counted: false,
    log: [],
    flash: null,
    shoppersPlayed: 0,
    seq: 1,
    external: false,
    touch: false,
    dwellFromVision: false,
    suggestions: [],
    suggestionVideo: '',
  }
}

export function begin(shopperIndex = 0, prev) {
  const event = shoppers[shopperIndex].events[0]
  return {
    shopperIndex,
    eventIndex: 0,
    phase: 'gaze',
    elapsed: 0,
    glances: 0,
    demoGlances: prev?.demoGlances ?? 0,
    seen: [event.productId],
    activeId: event.productId,
    dwellMs: 0,
    counted: false,
    log: prev?.log ?? [],
    flash: prev?.flash ?? null,
    shoppersPlayed: prev?.shoppersPlayed ?? 0,
    seq: prev?.seq ?? 1,
    external: prev?.external ?? false,
    touch: false,
    dwellFromVision: false,
  }
}

function decay(state, dt) {
  if (!state.flash) return state
  const ttl = state.flash.ttl - dt
  if (ttl <= 0) return { ...state, flash: null }
  return { ...state, flash: { ...state.flash, ttl } }
}

function countGlance(state, dwellMs) {
  if (state.counted || dwellMs < ASSUMPTIONS.glanceMs) return state
  return {
    ...state,
    counted: true,
    glances: state.glances + 1,
    demoGlances: state.demoGlances + 1,
  }
}

function closeLook(state, event) {
  const dwellMs = event.ms
  if (dwellMs < 150 && event.outcome !== 'purchase') {
    return { ...state, activeId: null, dwellMs: 0, counted: false }
  }
  const scored = analyse('week').byId[event.productId]
  const counted = countGlance(state, dwellMs)
  let kind = 'look'
  let text = 'Moved on'
  if (event.outcome === 'purchase') {
    kind = 'buy'
    text = 'Bought'
  } else if (event.outcome === 'leave' || dwellMs >= ASSUMPTIONS.nearMissMs) {
    kind = 'miss'
    text = scored?.title ?? 'Near-miss'
  } else if (dwellMs < ASSUMPTIONS.glanceMs) {
    kind = 'slide'
    text = 'Too brief to count'
  }

  const entry = {
    id: state.seq,
    kind,
    productId: event.productId,
    dwellMs,
    text,
    action: scored?.action ?? 'hold',
  }
  const flash =
    kind === 'miss' || kind === 'buy'
      ? { productId: event.productId, kind, ttl: 2800 }
      : state.flash

  return {
    ...counted,
    seq: state.seq + 1,
    log: [entry, ...state.log].slice(0, 14),
    flash,
    activeId: null,
    dwellMs: 0,
    counted: false,
  }
}

function finishMockEvent(state, event) {
  const closed = closeLook(state, event)
  const nextIndex = state.eventIndex + 1
  const more = nextIndex < shoppers[state.shopperIndex].events.length
  return {
    ...closed,
    phase: more ? 'gap' : 'between',
    elapsed: 0,
    eventIndex: more ? nextIndex : state.eventIndex,
    shoppersPlayed: more ? state.shoppersPlayed : state.shoppersPlayed + 1,
  }
}

function enterEvent(state) {
  const event = shoppers[state.shopperIndex].events[state.eventIndex]
  const seen = state.seen.includes(event.productId) ? state.seen : [...state.seen, event.productId]
  return {
    ...state,
    phase: 'gaze',
    elapsed: 0,
    dwellMs: 0,
    counted: false,
    activeId: event.productId,
    seen,
  }
}

function step(state, dt) {
  if (state.phase === 'gap' || state.phase === 'between') {
    const limit = state.phase === 'gap' ? GAP_MS : BETWEEN_MS
    const need = limit - state.elapsed
    if (dt < need) {
      return {
        state: { ...state, elapsed: state.elapsed + dt, activeId: null, dwellMs: 0 },
        leftover: 0,
      }
    }
    const next = state.phase === 'gap' ? enterEvent(state) : begin((state.shopperIndex + 1) % shoppers.length, state)
    return { state: next, leftover: dt - need }
  }

  const event = shoppers[state.shopperIndex].events[state.eventIndex]
  const need = event.ms - state.dwellMs
  if (dt < need) {
    const dwellMs = state.dwellMs + dt
    return { state: countGlance({ ...state, dwellMs, activeId: event.productId }, dwellMs), leftover: 0 }
  }
  const dwellMs = event.ms
  const atEnd = countGlance({ ...state, dwellMs, activeId: event.productId }, dwellMs)
  return { state: finishMockEvent(atEnd, event), leftover: dt - need }
}

export function advance(state, dt) {
  let current = decay(state, dt)
  let left = dt
  let guard = 0
  while (left > 0.5 && guard < 24) {
    guard += 1
    const result = step(current, left)
    if (result.leftover === left) break
    current = result.state
    left = result.leftover
  }
  return current
}

export function tickLive(state, dt) {
  let current = decay(state, dt)
  if (!current.activeId || current.dwellFromVision) return current
  const dwellMs = current.dwellMs + dt
  return countGlance({ ...current, dwellMs }, dwellMs)
}

export function applyLive(state, msg) {
  if (!msg || typeof msg !== 'object') return state
  if (msg.type === 'reset') {
    const fresh = begin(0, { ...state, shoppersPlayed: state.shoppersPlayed + 1, external: true })
    return { ...fresh, glances: 0, seen: [], activeId: null, dwellMs: 0, log: state.log }
  }
  if (msg.type === 'purchase') {
    const productId = asId(msg.name ?? msg.product ?? msg.productId) || state.activeId
    if (!productId) return state
    const closed = closeLook(
      { ...state, external: true },
      { productId, ms: state.activeId === productId ? state.dwellMs : ASSUMPTIONS.glanceMs, outcome: 'purchase' },
    )
    return { ...closed, external: true, phase: 'gap' }
  }
  if (msg.type === 'suggestions') {
    return {
      ...state,
      external: true,
      phase: 'gap',
      activeId: null,
      dwellMs: 0,
      touch: false,
      suggestions: Array.isArray(msg.items) ? msg.items : [],
      suggestionVideo: msg.video || '',
    }
  }
  if (msg.type === 'gaze') {
    const nextId = asId(msg.name ?? msg.product ?? msg.productId)
    const fromVision = msg.dwellMs != null && msg.dwellMs !== ''
    const reported = fromVision ? Number(msg.dwellMs) : null
    if (nextId === state.activeId) {
      if (!fromVision) return { ...state, touch: Boolean(msg.touch) }
      return countGlance({
        ...state,
        external: true,
        dwellFromVision: true,
        dwellMs: reported,
        touch: Boolean(msg.touch),
      }, reported)
    }
    let current = { ...state, external: true }
    if (state.activeId && state.external) {
      const outcome = state.dwellMs >= ASSUMPTIONS.nearMissMs ? 'leave' : undefined
      current = closeLook(current, { productId: state.activeId, ms: state.dwellMs, outcome })
    } else if (!state.external) {
      current = { ...current, activeId: null, dwellMs: 0, counted: false, flash: null, seen: [] }
    }
    if (!nextId) return { ...current, phase: 'gap', external: true, touch: false, dwellFromVision: fromVision }
    const seen = current.seen.includes(nextId) ? current.seen : [...current.seen, nextId]
    const dwellMs = reported ?? 0
    const opened = {
      ...current,
      phase: 'gaze',
      activeId: nextId,
      dwellMs,
      counted: false,
      seen,
      elapsed: 0,
      external: true,
      touch: Boolean(msg.touch),
      dwellFromVision: fromVision,
      suggestions: [],
      suggestionVideo: '',
    }
    return fromVision ? countGlance(opened, dwellMs) : opened
  }
  return state
}
