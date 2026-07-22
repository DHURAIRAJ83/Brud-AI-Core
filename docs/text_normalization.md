# Text normalization

Normalization is deterministic and conservative. All text uses Unicode NFC, CRLF/CR becomes LF, nulls and safe zero-width space/BOM characters are removed, horizontal whitespace is collapsed, outer whitespace is trimmed, and repeated blank lines are bounded. Punctuation, emoji, code-switching, Tamil letters, pulli, vowel marks, and combining sequences are preserved.

Tamil is never transliterated, lower-cased, spell-corrected, or stripped to an allowlist. Replacement characters, suspicious initial combining marks, and strong selected-language/script conflicts produce structured warnings. English stored content retains case; only its duplicate comparison form case-folds. Tanglish retains the submitted Latin text and only uses conservative whitespace/NFC plus a case-folded comparison form—no Tamil is invented. Mixed text preserves both Tamil and Latin scripts.

Each normalization result contains original and normalized text, comparison form, language, changed state, warnings, and original/normalized lengths. Full content is not logged. Phase 4 does not implement ML language detection or linguistic correction.
