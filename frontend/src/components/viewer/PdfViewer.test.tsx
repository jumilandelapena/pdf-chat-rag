import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { citation, document as doc } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { json, mockFetchRoutes } from '../../test/sse-response'
import { AssistantMessage } from '../chat/Messages'
import { PdfViewer } from './PdfViewer'

function setup(documents = [doc()]) {
  mockFetchRoutes({ 'GET /documents': () => json(documents) })
  return renderWithProviders(
    <>
      <AssistantMessage content="The pot returns 418. Done." citations={[citation({ text_end: 20 })]} usage={null} />
      <PdfViewer />
    </>,
  )
}

describe('PdfViewer', () => {
  it('opens the cited page and highlights the quote when a chip is clicked', async () => {
    setup()
    const user = userEvent.setup()
    expect(screen.getByText(/Click a citation/)).toBeInTheDocument()
    await user.click(screen.getByTestId('citation-chip'))
    await waitFor(() => expect(screen.getByTestId('viewer-page-indicator')).toHaveTextContent('Page 5 of 10'))
    expect(screen.getByTestId('pdf-page')).toHaveAttribute('data-page-number', '5')
    expect(screen.getByTestId('cited-passage')).toHaveTextContent('418')
    await waitFor(() => expect(document.querySelectorAll('mark.quote-hit').length).toBeGreaterThan(0))
    expect(screen.queryByText(/Exact text not found/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open PDF' })).toHaveAttribute('href', '/api/documents/d1/file')
  })

  it('clamps page navigation to the document length', async () => {
    setup()
    const user = userEvent.setup()
    await user.click(screen.getByTestId('citation-chip'))
    await screen.findByText('Page 5 of 10')
    const input = screen.getByLabelText('Page number')
    await user.clear(input)
    await user.type(input, '99')
    await waitFor(() => expect(screen.getByTestId('viewer-page-indicator')).toHaveTextContent('Page 10 of 10'))
    expect(screen.getByLabelText('Next page')).toBeDisabled()
    await user.click(screen.getByLabelText('Previous page'))
    expect(screen.getByTestId('viewer-page-indicator')).toHaveTextContent('Page 9 of 10')
  })

  it('reports when the cited text is not on the page', async () => {
    mockFetchRoutes({ 'GET /documents': () => json([doc()]) })
    renderWithProviders(
      <>
        <AssistantMessage content="x" citations={[citation({ quote: 'words that are not there', text_end: 1 })]} usage={null} />
        <PdfViewer />
      </>,
    )
    await userEvent.setup().click(screen.getByTestId('citation-chip'))
    expect(await screen.findByText(/Exact text not found/)).toBeInTheDocument()
  })

  it('shows a deleted state when the document is gone', async () => {
    setup([doc({ id: 'other' })])
    await userEvent.setup().click(screen.getByTestId('citation-chip'))
    expect(await screen.findByRole('alert')).toHaveTextContent('This document was deleted.')
  })
})
