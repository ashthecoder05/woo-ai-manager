from __future__ import annotations
"""
Marketing Engine

- Checklist-based content scoring
- Optimization loop: score → identify gaps → suggest improvements
- On-chain proof: generate verifiable marketing blocks from blockchain data
"""

import re
from dataclasses import dataclass, field
from typing import Any

from services import blockchain

# ---------------------------------------------------------------------------
# Checklist definition
# ---------------------------------------------------------------------------

@dataclass
class ChecklistItem:
    key: str
    description: str
    weight: int          # higher = more important
    patterns: list[str]  # regex patterns; any match = pass


CHECKLIST: list[ChecklistItem] = [
    ChecklistItem(
        key="mentions_bitcoin",
        description="Mentions Bitcoin or BTC as a payment option",
        weight=3,
        patterns=[r"\bbitcoin\b", r"\bbtc\b", r"₿"],
    ),
    ChecklistItem(
        key="has_cta",
        description="Contains a clear call-to-action",
        weight=3,
        patterns=[r"\bpay\b", r"\bbuy\b", r"\bshop\b", r"\bget\b", r"\border\b",
                  r"\bcheckout\b", r"\bpurchase\b", r"\bclaim\b", r"\bstart\b"],
    ),
    ChecklistItem(
        key="mentions_security",
        description="Highlights payment security or privacy",
        weight=2,
        patterns=[r"\bsecure\b", r"\bprivacy\b", r"\bprivate\b", r"\bsafe\b",
                  r"\bencrypt\b", r"\bno.?middleman\b", r"\bdirect\b"],
    ),
    ChecklistItem(
        key="mentions_speed",
        description="Mentions fast or instant transactions",
        weight=1,
        patterns=[r"\binstant\b", r"\bfast\b", r"\bquick\b", r"\bimmediate\b",
                  r"\bseconds\b", r"\bminutes\b"],
    ),
    ChecklistItem(
        key="non_custodial",
        description="Notes funds go directly to your wallet (non-custodial)",
        weight=2,
        patterns=[r"\bnon.?custodial\b", r"\bdirect.?to.?wallet\b", r"\byour.?wallet\b",
                  r"\bno.?third.?party\b", r"\bno.?intermediary\b"],
    ),
    ChecklistItem(
        key="has_social_proof",
        description="Includes social proof, verifiable data, or blockchain link",
        weight=2,
        patterns=[r"\bverif\w+\b", r"\bproven\b", r"\btransaction\b", r"\bblockchain\b",
                  r"\bon.?chain\b", r"mempool\.space", r"blockstream\.info",
                  r"\b\d+\s+customers\b", r"\b\d+\s+payments\b"],
    ),
    ChecklistItem(
        key="has_urgency",
        description="Creates urgency or highlights unique value",
        weight=1,
        patterns=[r"\bonly\b", r"\blimited\b", r"\bexclusive\b", r"\btoday\b",
                  r"\bnow\b", r"\bsave\b", r"\bdiscount\b", r"\boffer\b"],
    ),
    ChecklistItem(
        key="no_fees_or_low_fees",
        description="Mentions zero or low transaction fees",
        weight=1,
        patterns=[r"\bno\s+fee\b", r"\bzero\s+fee\b", r"\blow\s+fee\b",
                  r"\bfee.?free\b", r"\bno\s+extra\s+charge\b"],
    ),
]

CAMPAIGN_LENGTH_TARGETS: dict[str, tuple[int, int]] = {
    "product_description": (100, 400),
    "social": (20, 280),
    "email_subject": (5, 60),
    "email_body": (80, 600),
    "banner": (5, 30),
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class ChecklistResult:
    key: str
    description: str
    weight: int
    passed: bool
    matched_pattern: str | None = None


@dataclass
class ScoreReport:
    campaign_type: str
    content_length: int
    results: list[ChecklistResult]
    total_score: int
    max_score: int
    pct: float
    length_ok: bool
    gaps: list[str]           # descriptions of failed items
    suggestions: list[str]    # actionable suggestions


def score_content(content: str, campaign_type: str = "product_description") -> ScoreReport:
    """Score marketing copy against the checklist."""
    text = content.lower()
    results: list[ChecklistResult] = []
    total = 0
    max_score = 0

    for item in CHECKLIST:
        max_score += item.weight
        matched = None
        for pat in item.patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matched = m.group(0)
                break
        passed = matched is not None
        if passed:
            total += item.weight
        results.append(ChecklistResult(
            key=item.key,
            description=item.description,
            weight=item.weight,
            passed=passed,
            matched_pattern=matched,
        ))

    pct = round(total / max_score * 100, 1) if max_score else 0.0
    lo, hi = CAMPAIGN_LENGTH_TARGETS.get(campaign_type, (20, 1000))
    length_ok = lo <= len(content) <= hi

    gaps = [r.description for r in results if not r.passed]
    suggestions = _build_suggestions(results, campaign_type, length_ok, lo, hi, len(content))

    return ScoreReport(
        campaign_type=campaign_type,
        content_length=len(content),
        results=results,
        total_score=total,
        max_score=max_score,
        pct=pct,
        length_ok=length_ok,
        gaps=gaps,
        suggestions=suggestions,
    )


def _build_suggestions(
    results: list[ChecklistResult],
    campaign_type: str,
    length_ok: bool,
    lo: int,
    hi: int,
    actual_len: int,
) -> list[str]:
    tips: list[str] = []

    if not length_ok:
        if actual_len < lo:
            tips.append(f"Content is too short ({actual_len} chars). Aim for at least {lo} characters for a {campaign_type}.")
        else:
            tips.append(f"Content is too long ({actual_len} chars). Keep it under {hi} characters for a {campaign_type}.")

    key_tips = {
        "mentions_bitcoin": "Add 'Bitcoin' or 'BTC' explicitly so customers know they can pay with crypto.",
        "has_cta": "Add a clear action word like 'Pay with Bitcoin', 'Buy now', or 'Checkout'.",
        "mentions_security": "Highlight that payments are secure, private, or go directly to your wallet.",
        "mentions_speed": "Mention how fast Bitcoin payments settle (e.g., 'confirmed in minutes').",
        "non_custodial": "Tell customers funds go directly to your wallet — no middleman holds their money.",
        "has_social_proof": "Add a blockchain link or transaction count as verifiable proof (e.g., 'Verified on-chain').",
        "has_urgency": "Add urgency or value (e.g., 'Pay with BTC and save on fees today').",
        "no_fees_or_low_fees": "Mention that Bitcoin payments have low or no extra fees compared to credit cards.",
    }
    for r in results:
        if not r.passed and r.key in key_tips:
            tips.append(key_tips[r.key])

    return tips


def format_score_report(report: ScoreReport) -> str:
    grade = "A" if report.pct >= 85 else "B" if report.pct >= 70 else "C" if report.pct >= 50 else "D"
    lines = [
        f"Score: {report.total_score}/{report.max_score} ({report.pct}%) — Grade {grade}",
        f"Length: {report.content_length} chars {'✓' if report.length_ok else '✗ (target: see suggestions)'}",
        "",
        "Checklist:",
    ]
    for r in report.results:
        mark = "✓" if r.passed else "✗"
        lines.append(f"  {mark} [{r.weight}pt] {r.description}")

    if report.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for i, s in enumerate(report.suggestions, 1):
            lines.append(f"  {i}. {s}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optimization Loop
# ---------------------------------------------------------------------------

@dataclass
class OptimizationRound:
    round_number: int
    score_report: ScoreReport
    gaps_addressed: list[str]


@dataclass
class OptimizationPlan:
    """
    The optimization loop doesn't call Claude directly — it analyses the content,
    identifies gaps, and returns a structured plan that the Claude agent uses
    to rewrite the content intelligently.
    """
    original_content: str
    campaign_type: str
    initial_score: ScoreReport
    priority_gaps: list[str]     # top 3 most impactful gaps to fix
    rewrite_instructions: str    # plain-English instructions for rewriting


def build_optimization_plan(content: str, campaign_type: str = "product_description") -> OptimizationPlan:
    """
    Analyse content and build a structured rewrite plan.
    The agent uses this plan to ask Claude to rewrite the content.
    """
    report = score_content(content, campaign_type)

    # Sort failed items by weight (most impactful first)
    failed = sorted(
        [r for r in report.results if not r.passed],
        key=lambda r: r.weight,
        reverse=True,
    )
    priority_gaps = [r.description for r in failed[:3]]

    lo, hi = CAMPAIGN_LENGTH_TARGETS.get(campaign_type, (20, 1000))
    length_note = ""
    if not report.length_ok:
        if report.content_length < lo:
            length_note = f"Expand to at least {lo} characters. "
        else:
            length_note = f"Trim to under {hi} characters. "

    instructions = (
        f"Rewrite the following {campaign_type} to score higher on this checklist. "
        f"{length_note}"
        f"Priority improvements needed: {'; '.join(priority_gaps) if priority_gaps else 'none — just polish'}. "
        f"Keep the same product/service focus. Output only the rewritten copy, no commentary."
    )

    return OptimizationPlan(
        original_content=content,
        campaign_type=campaign_type,
        initial_score=report,
        priority_gaps=priority_gaps,
        rewrite_instructions=instructions,
    )


# ---------------------------------------------------------------------------
# On-Chain Proof Marketing
# ---------------------------------------------------------------------------

EXPLORER_BASE = "https://mempool.space"


@dataclass
class ProofBlock:
    """A verifiable, on-chain fact usable in marketing copy."""
    claim: str               # human-readable claim
    proof_url: str           # blockchain explorer link
    verified: bool           # did we actually confirm this from chain data?
    raw: dict = field(default_factory=dict)


def generate_proof_block(txid: str) -> ProofBlock:
    """
    Fetch a transaction and turn it into a verifiable marketing claim.
    E.g., "Payment of 0.05 BTC confirmed on Bitcoin block 840,000"
    """
    try:
        tx = blockchain.get_transaction(txid)
    except Exception as e:
        return ProofBlock(
            claim=f"Transaction {txid[:16]}... (could not verify: {e})",
            proof_url=f"{EXPLORER_BASE}/tx/{txid}",
            verified=False,
        )

    if tx["confirmed"]:
        height = tx.get("block_height") or "unknown block"
        claim = (
            f"Payment verified on the Bitcoin blockchain "
            f"(block {height:,} — {tx['fee_rate_sat_vbyte']} sat/vB)"
        )
    else:
        claim = f"Payment of {tx['vsize_vbytes']} vBytes seen in mempool (awaiting confirmation)"

    return ProofBlock(
        claim=claim,
        proof_url=f"{EXPLORER_BASE}/tx/{txid}",
        verified=tx["confirmed"],
        raw=tx,
    )


def generate_address_proof(address: str, confirmed_satoshis: int, tx_count: int) -> ProofBlock:
    """
    Generate a proof block from address-level data (balance + tx count).
    Suitable for 'total volume processed' type marketing.
    """
    btc = confirmed_satoshis / 1e8
    claim = (
        f"Over {btc:.4f} BTC processed across {tx_count} verified transactions — "
        f"all publicly auditable on the Bitcoin blockchain."
    )
    return ProofBlock(
        claim=claim,
        proof_url=f"{EXPLORER_BASE}/address/{address}",
        verified=True,
        raw={"address": address, "confirmed_satoshis": confirmed_satoshis, "tx_count": tx_count},
    )


def inject_proof_into_copy(copy: str, proof: ProofBlock) -> str:
    """Append a verifiable proof statement and link to marketing copy."""
    proof_line = f"\n\n🔗 Verified on-chain: {proof.claim}\nSee proof: {proof.proof_url}"
    return copy.rstrip() + proof_line


def format_proof_for_agent(proof: ProofBlock) -> str:
    status = "verified on-chain" if proof.verified else "unverified"
    return (
        f"Claim: {proof.claim}\n"
        f"Status: {status}\n"
        f"Explorer URL: {proof.proof_url}"
    )
