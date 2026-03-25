/**
 * Composable for managing sticky elements based on the position of a base element.
 */

export function useSticky(
  targetReference: Ref<HTMLElement | unknown>,
  options: {
    /** Base element selector for calculating sticky offset */
    baseElementSelector: string
    /**
     * Space in rem units between the sticky element and the base element
     * @default 1
      */
    spaceRem?: number
    /**
     * Fallback position (in pixels) if the base element is not found
     * @default 0
     */
    fallbackPosition?: number
  },
) {
  const isStuck = ref(false)
  let observer: IntersectionObserver | undefined

  const initStickyObserver = () => {
    if (observer) observer.disconnect()

    const style = getComputedStyle(document.documentElement)

    const baseElement = document.querySelector(options.baseElementSelector)
    const basePositon = baseElement
      ? baseElement.getBoundingClientRect().height
      : options.fallbackPosition || 0

    const remPx = Number.parseFloat(style.fontSize) || 16
    const buffer = 1
    const offset = basePositon + (options.spaceRem || 1) * remPx + buffer

    observer = new IntersectionObserver(
      ([entry]) => {
        isStuck.value = entry ? entry.intersectionRatio < 1 : false
      },
      {
        threshold: [1],
        rootMargin: `-${offset}px 0px 0px 0px`,
      },
    )

    if (targetReference.value) {
      observer.observe(targetReference.value as HTMLElement)
    }
  }

  onMounted(() => {
    initStickyObserver()
    window.addEventListener('resize', initStickyObserver)
  })

  onUnmounted(() => {
    observer?.disconnect()
    window.removeEventListener('resize', initStickyObserver)
  })

  return { isStuck }
}
