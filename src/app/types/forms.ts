type UseSelectMenuInfiniteScrollOptions<T> = {
  url: string
  limit?: number
  transform: (item: T) => { label: string, value: string }
  debounce?: number
  scrollDistance?: number
  query?: Record<string, string | number | boolean>
  server?: boolean
}

type UseSelectMenuInfiniteScrollReturn = {
  items: Ref<Array<{ label: string, value: string }>>
  searchTerm: Ref<string>
  status: Ref<'idle' | 'pending' | 'success' | 'error'>
  onOpen: (isOpen: boolean) => void
  setupInfiniteScroll: (
    selectMenuReference: Ref<unknown>,
  ) => void
}

export type {
  UseSelectMenuInfiniteScrollOptions,
  UseSelectMenuInfiniteScrollReturn,
}
