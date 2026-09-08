"""
Canonical Brud AI Model Architecture Definitions.
Authoritative source of truth for:
  - BrudSmallV2Model (528,128 parameters; T=128 or T=512)
  - BrudSmallScaledModel (3,159,040 parameters; L=4, d=256, h=8, d_ff=768, T=512)

Governance:
  - Static PE buffer is registered with persistent=False (prevents unexpected PE keys in state_dict)
  - Programmatic parameter count calculation methods provided
  - Supports raw forward evaluation and controlled repetition-free decoding (theta=1.25, 3-gram)
"""

import math
import torch
import torch.nn as nn
from typing import Dict, Any, Optional, List


class BrudSmallV2Model(nn.Module):
    """Authoritative Brud-Small v2 Decoder-Only Causal Transformer (528,128 parameters)."""

    def __init__(
        self,
        vocab_size: int = 1024,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 256,
        max_seq: int = 128
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.dim_feedforward = dim_feedforward
        self.max_seq = max_seq

        self.embedding = nn.Embedding(vocab_size, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            batch_first=True,
            norm_first=False,
            dropout=0.0,
            activation="relu"
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=True)
        self.register_buffer("pe", self._build_sinusoidal_pe(max_seq, d_model), persistent=False)

    @staticmethod
    def _build_sinusoidal_pe(max_len: int, d_model: int) -> torch.Tensor:
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        return pe.unsqueeze(0)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        seq_len = x.size(1)
        h = self.embedding(x) + self.pe[:, :seq_len, :]
        if mask is not None:
            h = self.encoder(h, mask=mask)
        else:
            h = self.encoder(h)
        return self.lm_head(h)

    def get_parameter_count(self) -> Dict[str, int]:
        total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        emb_params = self.embedding.weight.numel()
        layer_params = sum(p.numel() for p in self.encoder.parameters() if p.requires_grad)
        head_params = sum(p.numel() for p in self.lm_head.parameters() if p.requires_grad)
        return {
            "total_trainable_parameters": total_params,
            "embedding_parameters": emb_params,
            "encoder_parameters": layer_params,
            "head_parameters": head_params
        }

    def generate_controlled(
        self,
        sp: Any,
        prompt: str,
        max_new_tokens: int = 48,
        temperature: float = 0.7,
        top_k: int = 20,
        rep_penalty: float = 1.25,
        no_repeat_ngram: int = 3
    ) -> Dict[str, Any]:
        self.eval()
        input_text = f"<user>{prompt}<assistant>"
        ids = sp.encode(input_text, out_type=int)
        x = torch.tensor([ids], dtype=torch.long)
        gen_tokens: List[int] = []

        with torch.no_grad():
            for _ in range(max_new_tokens):
                if x.size(1) >= self.max_seq:
                    break
                seq_len = x.size(1)
                mask = nn.Transformer.generate_square_subsequent_mask(seq_len)
                logits = self.forward(x, mask=mask)
                next_logits = logits[0, -1, :].clone()

                # Repetition Penalty
                if rep_penalty > 1.0 and len(gen_tokens) > 0:
                    for tok in set(gen_tokens):
                        if next_logits[tok] > 0:
                            next_logits[tok] /= rep_penalty
                        else:
                            next_logits[tok] *= rep_penalty

                # No-Repeat N-Gram Filter
                if no_repeat_ngram > 0 and len(gen_tokens) >= no_repeat_ngram - 1:
                    full_seq = ids + gen_tokens
                    ngram_prefix = tuple(full_seq[-(no_repeat_ngram - 1):])
                    banned_tokens = set()
                    for i in range(len(full_seq) - no_repeat_ngram + 1):
                        if tuple(full_seq[i:i + no_repeat_ngram - 1]) == ngram_prefix:
                            banned_tokens.add(full_seq[i + no_repeat_ngram - 1])
                    for b_tok in banned_tokens:
                        next_logits[b_tok] = -float("inf")

                # Top-K Sampling
                if top_k > 0:
                    v, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                    next_logits[next_logits < v[-1]] = -float("inf")

                if temperature > 0.0:
                    probs = torch.softmax(next_logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1).item()
                else:
                    next_token = next_logits.argmax().item()

                if next_token == 3:  # EOS token
                    break
                gen_tokens.append(next_token)
                x = torch.cat([x, torch.tensor([[next_token]], dtype=torch.long)], dim=1)

        decoded = sp.decode(gen_tokens)
        return {
            "prompt": prompt,
            "token_count": len(gen_tokens),
            "tokens": gen_tokens,
            "decoded": decoded,
            "eos_emitted": (len(gen_tokens) < max_new_tokens and x.size(1) < self.max_seq)
        }


class BrudSmallScaledModel(nn.Module):
    """Authoritative Brud-Small Scaled Model (E5 Architecture: 3,159,040 parameters; L=4, d=256, h=8, d_ff=768, T=512)."""

    def __init__(
        self,
        vocab_size: int = 1024,
        d_model: int = 256,
        nhead: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 768,
        max_seq: int = 512
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.dim_feedforward = dim_feedforward
        self.max_seq = max_seq

        self.embedding = nn.Embedding(vocab_size, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            batch_first=True,
            norm_first=False,
            dropout=0.0,
            activation="relu"
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=True)
        self.register_buffer("pe", self._build_sinusoidal_pe(max_seq, d_model), persistent=False)

    @staticmethod
    def _build_sinusoidal_pe(max_len: int, d_model: int) -> torch.Tensor:
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        return pe.unsqueeze(0)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        seq_len = x.size(1)
        h = self.embedding(x) + self.pe[:, :seq_len, :]
        if mask is not None:
            h = self.encoder(h, mask=mask)
        else:
            h = self.encoder(h)
        return self.lm_head(h)

    def get_parameter_count(self) -> Dict[str, int]:
        total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        emb_params = self.embedding.weight.numel()
        layer_params = sum(p.numel() for p in self.encoder.parameters() if p.requires_grad)
        head_params = sum(p.numel() for p in self.lm_head.parameters() if p.requires_grad)
        return {
            "total_trainable_parameters": total_params,
            "embedding_parameters": emb_params,
            "encoder_parameters": layer_params,
            "head_parameters": head_params
        }

    def generate_controlled(
        self,
        sp: Any,
        prompt: str,
        max_new_tokens: int = 48,
        temperature: float = 0.7,
        top_k: int = 20,
        rep_penalty: float = 1.25,
        no_repeat_ngram: int = 3
    ) -> Dict[str, Any]:
        self.eval()
        input_text = f"<user>{prompt}<assistant>"
        ids = sp.encode(input_text, out_type=int)
        x = torch.tensor([ids], dtype=torch.long)
        gen_tokens: List[int] = []

        with torch.no_grad():
            for _ in range(max_new_tokens):
                if x.size(1) >= self.max_seq:
                    break
                seq_len = x.size(1)
                mask = nn.Transformer.generate_square_subsequent_mask(seq_len)
                logits = self.forward(x, mask=mask)
                next_logits = logits[0, -1, :].clone()

                if rep_penalty > 1.0 and len(gen_tokens) > 0:
                    for tok in set(gen_tokens):
                        if next_logits[tok] > 0:
                            next_logits[tok] /= rep_penalty
                        else:
                            next_logits[tok] *= rep_penalty

                if no_repeat_ngram > 0 and len(gen_tokens) >= no_repeat_ngram - 1:
                    full_seq = ids + gen_tokens
                    ngram_prefix = tuple(full_seq[-(no_repeat_ngram - 1):])
                    banned_tokens = set()
                    for i in range(len(full_seq) - no_repeat_ngram + 1):
                        if tuple(full_seq[i:i + no_repeat_ngram - 1]) == ngram_prefix:
                            banned_tokens.add(full_seq[i + no_repeat_ngram - 1])
                    for b_tok in banned_tokens:
                        next_logits[b_tok] = -float("inf")

                if top_k > 0:
                    v, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                    next_logits[next_logits < v[-1]] = -float("inf")

                if temperature > 0.0:
                    probs = torch.softmax(next_logits / temperature, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1).item()
                else:
                    next_token = next_logits.argmax().item()

                if next_token == 3:
                    break
                gen_tokens.append(next_token)
                x = torch.cat([x, torch.tensor([[next_token]], dtype=torch.long)], dim=1)

        decoded = sp.decode(gen_tokens)
        return {
            "prompt": prompt,
            "token_count": len(gen_tokens),
            "tokens": gen_tokens,
            "decoded": decoded,
            "eos_emitted": (len(gen_tokens) < max_new_tokens and x.size(1) < self.max_seq)
        }
