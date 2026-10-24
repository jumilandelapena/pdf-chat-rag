/** Minimal typings for the subset of gifenc used by scripts/demo-gif.ts. */
declare module 'gifenc' {
  export type Palette = number[][]

  export interface FrameOptions {
    palette?: Palette
    delay?: number
    repeat?: number
    transparent?: boolean
    transparentIndex?: number
    dispose?: number
    first?: boolean
  }

  export interface Encoder {
    writeFrame(index: Uint8Array, width: number, height: number, options?: FrameOptions): void
    finish(): void
    bytes(): Uint8Array
    reset(): void
  }

  export function GIFEncoder(options?: { auto?: boolean; initialCapacity?: number }): Encoder
  export function quantize(
    rgba: Uint8Array | Uint8ClampedArray,
    maxColors: number,
    options?: { format?: 'rgb565' | 'rgb444' | 'rgba4444' },
  ): Palette
  export function applyPalette(
    rgba: Uint8Array | Uint8ClampedArray,
    palette: Palette,
    format?: 'rgb565' | 'rgb444' | 'rgba4444',
  ): Uint8Array

  const gifenc: {
    GIFEncoder: typeof GIFEncoder
    quantize: typeof quantize
    applyPalette: typeof applyPalette
  }
  export default gifenc
}
