import { describe, expect, it } from 'vitest'
import {
  DOCUMENT_NAV_TARGETS, buildDocumentsHash, buildWizardHash, isKnownDocumentsTabKey, parseHash,
  resolveDocumentNavigation,
} from './documentNavigation.js'

describe('documentNavigation: parseHash', () => {
  it('parses a page name with no query string', () => {
    expect(parseHash('Documents')).toEqual({ page: 'Documents', documentPublicId: null, tab: null, step: null })
  })

  it('parses document and tab query params', () => {
    expect(parseHash('Documents?document=doc-1&tab=security-review')).toEqual({
      page: 'Documents', documentPublicId: 'doc-1', tab: 'security-review', step: null,
    })
  })

  it('parses a numeric wizard step', () => {
    const parsed = parseHash(encodeURIComponent('Document Wizard') + '?document=doc-1&step=11')
    expect(parsed).toEqual({ page: 'Document Wizard', documentPublicId: 'doc-1', tab: null, step: 11 })
  })

  it('ignores a non-numeric step value rather than trusting it', () => {
    const parsed = parseHash('Document Wizard?document=doc-1&step=<script>')
    expect(parsed.step).toBeNull()
  })

  it('defaults to Overview for an empty hash', () => {
    expect(parseHash('')).toEqual({ page: 'Overview', documentPublicId: null, tab: null, step: null })
  })

  it('never treats the query string as anything other than the two known keys', () => {
    const parsed = parseHash('Documents?document=doc-1&tab=security-review&__proto__=polluted&onerror=alert(1)')
    expect(parsed).toEqual({ page: 'Documents', documentPublicId: 'doc-1', tab: 'security-review', step: null })
  })
})

describe('documentNavigation: hash builders', () => {
  it('builds a Documents hash with document and tab', () => {
    expect(buildDocumentsHash('doc-1', 'security-review')).toBe('#Documents?document=doc-1&tab=security-review')
  })

  it('builds a Documents hash with no params when nothing is given', () => {
    expect(buildDocumentsHash(null, null)).toBe('#Documents')
  })

  it('builds a Wizard hash with document and numeric step', () => {
    expect(buildWizardHash('doc-1', 11)).toBe(`#${encodeURIComponent('Document Wizard')}?document=doc-1&step=11`)
  })

  it('round-trips through parseHash', () => {
    const hash = buildDocumentsHash('doc-9', 'dataset-handoff')
    const parsed = parseHash(hash.slice(1))
    expect(parsed.documentPublicId).toBe('doc-9')
    expect(parsed.tab).toBe('dataset-handoff')
  })
})

describe('documentNavigation: resolveDocumentNavigation', () => {
  it('resolves a known key with the document id attached', () => {
    expect(resolveDocumentNavigation('security-review', 'doc-1')).toEqual({
      navKey: 'Documents', documentsTab: 'Security Review', tabKey: 'security-review', documentPublicId: 'doc-1',
    })
  })

  it('resolves a wizard-step key', () => {
    expect(resolveDocumentNavigation('dataset-handoff', 'doc-1')).toEqual({
      navKey: 'Document Wizard', wizardStep: 11, tabKey: 'dataset-handoff', documentPublicId: 'doc-1',
    })
  })

  it('returns null for an unknown key rather than fabricating a route', () => {
    expect(resolveDocumentNavigation('history', 'doc-1')).toBeNull()
    expect(resolveDocumentNavigation('made-up-key', 'doc-1')).toBeNull()
  })

  it('every registered target maps to a documentsTab or a wizardStep or neither (plain page), never both', () => {
    for (const target of Object.values(DOCUMENT_NAV_TARGETS)) {
      expect(target.documentsTab && target.wizardStep).toBeFalsy()
    }
  })
})

describe('documentNavigation: isKnownDocumentsTabKey', () => {
  it('is true only for Documents-page semantic keys', () => {
    expect(isKnownDocumentsTabKey('security-review')).toBe(true)
    expect(isKnownDocumentsTabKey('dataset-handoff')).toBe(false)
    expect(isKnownDocumentsTabKey('history')).toBe(false)
  })
})
