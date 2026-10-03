import { useEffect, useRef, useState } from 'react'
import { shoppers } from './model'
import { advance, applyLive, begin, idle, tickLive } from './playback'

export function useAisle() {
  const cursor = useRef(idle())
  const [snap, setSnap] = useState(cursor.current)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [feed, setFeed] = useState('waiting')
  const playingRef = useRef(false)
  const speedRef = useRef(1)
  const externalRef = useRef(false)

  useEffect(() => {
    playingRef.current = playing
  }, [playing])

  useEffect(() => {
    speedRef.current = speed
  }, [speed])

  useEffect(() => {
    const publish = (next) => {
      cursor.current = next
      setSnap(next)
    }

    const push = (msg) => {
      externalRef.current = true
      setFeed('live')
      setPlaying(false)
      publish(applyLive(cursor.current, msg))
    }

    window.NearMiss = {
      gaze(productId) {
        push({ type: 'gaze', productId: productId || null })
      },
      purchase(productId) {
        push({ type: 'purchase', productId })
      },
      reset() {
        push({ type: 'reset' })
      },
    }

    const requested = new URLSearchParams(window.location.search).get('feed')
    const feedUrl = requested === 'off' ? '' : (requested || 'ws://127.0.0.1:8765')
    let socket
    let retry
    let stopped = false
    const connect = () => {
      if (stopped || !feedUrl) return
      try {
        socket = new WebSocket(feedUrl)
      } catch {
        retry = window.setTimeout(connect, 1500)
        return
      }
      socket.onmessage = (event) => {
        try {
          push(JSON.parse(event.data))
        } catch {
          /* ignore malformed frames */
        }
      }
      socket.onclose = () => {
        setFeed((current) => (current === 'live' ? 'error' : current))
        if (!stopped) retry = window.setTimeout(connect, 1500)
      }
    }
    connect()

    let frame = 0
    let last = performance.now()
    const loop = (now) => {
      const dt = Math.min(48, now - last)
      last = now
      if (externalRef.current) {
        publish(tickLive(cursor.current, dt))
      } else if (playingRef.current) {
        publish(advance(cursor.current, dt * speedRef.current))
      }
      frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)

    return () => {
      stopped = true
      window.clearTimeout(retry)
      cancelAnimationFrame(frame)
      if (socket) socket.close()
      delete window.NearMiss
    }
  }, [])

  return {
    snap,
    playing,
    setPlaying,
    speed,
    setSpeed,
    feed,
    playSample() {
      externalRef.current = false
      setFeed('mock')
      const next = begin(0)
      cursor.current = next
      setSnap(next)
      setPlaying(true)
    },
    restart() {
      externalRef.current = false
      setFeed('mock')
      const next = begin(0)
      cursor.current = next
      setSnap(next)
      setPlaying(true)
    },
    nextShopper() {
      if (externalRef.current) return
      const started = cursor.current.activeId || cursor.current.seen.length || cursor.current.log.length
      const index = started ? (cursor.current.shopperIndex + 1) % shoppers.length : 0
      const next = begin(index, started ? {
        ...cursor.current,
        shoppersPlayed: cursor.current.shoppersPlayed + 1,
      } : undefined)
      externalRef.current = false
      setFeed('mock')
      setPlaying(true)
      cursor.current = next
      setSnap(next)
    },
  }
}
