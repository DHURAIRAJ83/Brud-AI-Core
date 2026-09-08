# Phase 58 Special Token & Masking Contract

**Workstream:** 12 — Special Token & Masking Contract  
**Timestamp:** 2026-08-30T17:50:00Z  
**Status:** ✅ CANONICAL CONTRACT ESTABLISHED

---

## 1. Canonical Special Token Table

| Token Piece | Token ID | Semantics & Role | Collision Safeguard | PyTorch CrossEntropy Policy |
|---|---|---|---|---|
| `<pad>` | **0** | Padding token for batch alignment | Reserved index 0; never emitted for text | `ignore_index = 0` (Loss = 0) |
| `<unk>` | **1** | Unknown fallback token | Reserved index 1; bypassed via byte fallback | Active in loss, but should occur at 0% |
| `<s>` | **2** | Beginning of Sequence (BOS) | Reserved index 2; marks generation initiation | Masked or unmasked depending on stage |
| `</s>` | **3** | End of Sequence (EOS) | Reserved index 3; signals generation termination | Active in loss (target prediction) |
| `<system>` | **4** | System instruction turn delimiter | Reserved index 4; delimiter token | Masked in loss (`ignore_index`) |
| `<user>` | **5** | User prompt turn delimiter | Reserved index 5; delimiter token | Masked in loss (`ignore_index`) |
| `<assistant>` | **6** | Assistant response turn delimiter | Reserved index 6; triggers response loss | Loss computation starts immediately after |
| `<ta>` | **7** | Tamil language identification prefix | Reserved index 7; conditioning token | Conditioning prefix |
| `<en>` | **8** | English language identification prefix | Reserved index 8; conditioning prefix | Conditioning prefix |
| `<tgl>` | **9** | Tanglish language identification prefix| Reserved index 9; conditioning prefix | Conditioning prefix |
| `<mixed>` | **10** | Bilingual / code-switched prefix | Reserved index 10; conditioning prefix | Conditioning prefix |
| `<0x00>..<0xFF>`| **11..266** | 256 raw UTF-8 byte pieces | Covers all unindexed Unicode bytes | Loss calculated normally |

---

## 2. Masking Contract for Future Training

In future instruction/SFT training:
1. **Prompt Masking:**
   $$\text{Mask}(t) = \begin{cases} 0 & \text{if } t \le t_{\text{assistant}} \quad (\text{Prompt tokens ignored}) \\ 1 & \text{if } t > t_{\text{assistant}} \quad (\text{Response tokens evaluated}) \end{cases}$$
2. **Padding Masking:**
   Any position where $x_t = 0$ is assigned target label `-100` or handled via `ignore_index = 0`.
3. **EOS Contract:**
   Every training sequence concludes with `</s>` (ID 3), teaching the model when to stop speaking.
