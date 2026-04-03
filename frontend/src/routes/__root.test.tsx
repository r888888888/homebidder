import { describe, expect, it, vi } from 'vitest'

vi.mock('@tanstack/react-router', () => ({
  createRootRoute: (config: unknown) => config,
  HeadContent: () => null,
  Scripts: () => null,
}))

describe('Root route head', () => {
  it('includes favicon links using the header icon asset', async () => {
    const { Route } = await import('./__root')
    const head = (Route as { head: () => { links?: Array<Record<string, string>> } }).head()

    expect(head.links).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          rel: 'icon',
          href: '/header-icon.svg',
          type: 'image/svg+xml',
        }),
      ]),
    )
  })
})
