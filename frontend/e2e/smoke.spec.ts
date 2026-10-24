import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const RFC_PDF = fileURLToPath(new URL('../../sample-pdfs/rfc2324-htcpcp.pdf', import.meta.url))

test('upload, ask, cite, open the page', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Upload PDFs')).toBeVisible()
  await page.getByRole('button', { name: 'New chat' }).click()

  const name = `rfc2324-${Date.now()}.pdf`
  await page.getByLabel('Upload PDFs').setInputFiles({
    name,
    mimeType: 'application/pdf',
    buffer: readFileSync(RFC_PDF),
  })
  const row = page.getByTestId('doc-row').filter({ hasText: name })
  await expect(row.getByTestId('doc-status')).toHaveAttribute('data-status', 'ready', { timeout: 120_000 })
  await expect(row).toContainText('10 pages')

  const box = page.getByLabel('Ask a question')
  await expect(box).toBeEnabled()
  await box.fill('What error code is returned when you try to brew coffee with a teapot?')
  await page.keyboard.press('Enter')

  const answer = page.getByTestId('assistant-message').last()
  await expect(answer).toContainText('Based on the uploaded documents', { timeout: 60_000 })
  await expect(answer.getByTestId('cost-line')).toContainText('(mock)')

  const chip = answer.getByTestId('citation-chip').first()
  await expect(chip).toBeVisible()
  const cited = Number(await chip.getAttribute('data-page'))
  await chip.click()
  await expect(page.getByTestId('viewer-page-indicator')).toHaveText(new RegExp(`^Page ${cited} of \d+`), {
    timeout: 30_000,
  })
  await expect(page.getByTestId('cited-passage')).toBeVisible()
  await expect(page.locator('.react-pdf__Page__textContent mark.quote-hit').first()).toBeVisible({ timeout: 30_000 })

  await page.reload()
  await expect(page.getByTestId('assistant-message').last()).toContainText('Based on the uploaded documents')
  await expect(page.getByTestId('citation-chip').first()).toBeVisible()
})

test.describe('mobile', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('stacks the three panels vertically', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByLabel('Upload PDFs')).toBeVisible()
    const boxes = await Promise.all(
      ['Documents', 'Chat', 'PDF viewer'].map((name) => page.getByRole('region', { name }).boundingBox()),
    )
    const [docs, chat, viewer] = boxes
    expect(docs && chat && viewer).toBeTruthy()
    expect(docs!.y).toBeLessThan(chat!.y)
    expect(chat!.y).toBeLessThan(viewer!.y)
    for (const box of boxes) {
      expect(box!.x).toBe(docs!.x)
      expect(box!.width).toBeLessThanOrEqual(375)
    }
  })
})
