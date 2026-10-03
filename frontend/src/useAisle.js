import { useEffect, useRef, useState } from 'react'
import { shoppers } from './model'
import { advance, applyLive, begin, tickLive } from './playback'

export function useAisle() {
  const cursor = useRef(begin(0))
  const [snap, setSnap] = useState(cursor.current)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [feed, setFeed] = useState('mock')
  const playingRef = useRef(true)
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

    const feedUrl = new URLSearchParams(window.location.search).get('feed')
    let socket
    if (feedUrl) {
      setFeed('connecting')
      try {
        socket = new WebSocket(feedUrl)
        socket.onopen = () => setFeed('live')
        socket.onerror = () => setFeed('error')
        socket.onclose = () => setFeed((current) => (current === 'live' ? 'error' : current))
        socket.onmessage = (event) => {
          try {
            push(JSON.parse(event.data))
          } catch {
            /* ignore malformed frames */
          }
        }
      } catch {
        setFeed('error')
      }
    }

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
      const next = begin((cursor.current.shopperIndex + 1) % shoppers.length, {
        ...cursor.current,
        shoppersPlayed: cursor.current.shoppersPlayed + 1,
      })
      cursor.current = next
      setSnap(next)
    },
  }
}
