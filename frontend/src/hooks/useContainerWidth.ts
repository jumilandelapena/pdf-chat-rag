import { useEffect, useRef, useState, type RefObject } from 'react'

/** Width of a container element, tracked with ResizeObserver (falls back in jsdom). */
export function useContainerWidth<T extends HTMLElement>(fallback = 600): [RefObject<T>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const update = () => setWidth(el.clientWidth || fallback)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [fallback])
  return [ref, width]
}
