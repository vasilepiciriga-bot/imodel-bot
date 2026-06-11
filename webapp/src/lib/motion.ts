export const spring = { type: 'spring' as const, stiffness: 380, damping: 28 }
export const springFast = { type: 'spring' as const, stiffness: 500, damping: 32 }

export const tap96 = { whileTap: { scale: 0.96 } }
export const tap97 = { whileTap: { scale: 0.97 } }
export const tap98 = { whileTap: { scale: 0.98 } }

export const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -8 },
  transition: spring,
}

export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit:    { opacity: 0 },
}

export const scaleIn = {
  initial: { scale: 0.85, opacity: 0 },
  animate: { scale: 1, opacity: 1 },
  exit:    { scale: 0.9, opacity: 0 },
  transition: spring,
}

export const slideUp = {
  initial: { y: '100%', opacity: 0 },
  animate: { y: 0, opacity: 1 },
  exit:    { y: '100%', opacity: 0 },
  transition: spring,
}

export const stagger = (i: number) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: i * 0.045, ...spring },
})
