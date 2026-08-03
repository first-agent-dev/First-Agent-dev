"""S10c.4/S10c.5 — composer request contracts: no silent drops, no wasted bytes.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S10c-contract-and-posture-fixes.md``

**CT4 — no key is emitted that its destination silently drops (I-39).**
``to_openai_request_v2`` injects ``prompt_cache_key`` and
``prompt_cache_retention`` into ``extra_body`` on every request. The Mistral
adapter filters ``provider_params`` against a fixed recognised set, and
``prompt_cache_retention`` is not in it — so the hint reaches
OpenAI-compatible routes and is silently discarded on Mistral ones.

``routing_lint`` check 3 already validates ``provider_params`` **declared in
models.yaml** against those same sets, but composer-injected extras never pass
through it. A key the composer invents and an adapter drops was invisible to
every existing check. That invisibility — not the dropped key itself — is the
defect this module closes.

**Q55 (operator): Mistral is a temporary test provider, best-effort only.** So
the pair is not "fixed" by adding the key (that would claim unverified support)
or by removing the emit (that would penalise routes where it works). It is
recorded in ``_KNOWN_UNRECOGNISED`` and asserted, which keeps the gate binary:
a *second*, unplanned silent drop still fails.

**CT5 — the inline tool block is compact.** Whitespace-only change worth 29.6%
of that block on every request.

Test classes: **C1** (static configuration contract), **C0p** (pure encoder).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fa.inner_loop.prompt import render_tool_specs
from fa.inner_loop.prompt_composer import (
    COMPOSER_EXTRA_BODY_KEYS,
    PromptParts,
    build_prompt_parts_v2,
    to_openai_request_v2,
)
from fa.inner_loop.tools import build_baseline_registry
from fa.providers.routing_lint import KNOWN_PROVIDER_PARAMS_KEYS

# Composer-emitted keys a destination adapter is KNOWN not to recognise, with
# the reason. Every entry is a deliberate, reviewed exception; anything absent
# from this table and from the adapter's recognised set is a contract failure.
#
# Adding a row here is a decision, not a formality: it means "we accept that
# this key is discarded on this route". Removing the last row must leave the
# test still meaningful, which is why the emptiness of the *residual* set is
# what is asserted rather than the allow-list's contents.
_MISTRAL_RETENTION_REASON = (
    "Q55: Mistral is a temporary test provider — best-effort only. "
    "'prompt_cache_retention' is absent from this adapter's recognised set and is "
    "dropped when the request body is built. Deliberately NOT added (that would "
    "claim API support nobody has verified) and NOT removed from the composer "
    "(it works on openai_compat routes, asserted in "
    "tests/test_providers_openai_compat.py). Revisit when a Mistral route is "
    "promoted out of 'temporary test'."
)

_KNOWN_UNRECOGNISED: dict[tuple[str, str], str] = {
    ("mistral", "prompt_cache_retention"): _MISTRAL_RETENTION_REASON,
    # Found BY THIS GATE on first run (S10c.4). I-39 documented the drop for
    # `mistral` only; `mistral_agents` has the identical gap — it recognises
    # `prompt_cache_key` but not `prompt_cache_retention`. Verified against
    # MISTRAL_CONVERSATIONS_RECOGNIZED_PROVIDER_PARAMS_KEYS rather than assumed
    # from the family name. Same Q55 rationale applies.
    ("mistral_agents", "prompt_cache_retention"): _MISTRAL_RETENTION_REASON,
}


def test_s10c_composer_extras_match_the_emitted_request() -> None:
    """C1 (S10c.4 / CT4 / RK10): the exported constant IS what the function emits.

    Without this the contract test below would validate a fiction: the constant
    could drift from the dict literal inside ``to_openai_request_v2`` and every
    downstream assertion would still pass while checking the wrong key set.

    Oracle: the emitted ``extra_body`` keys equal ``COMPOSER_EXTRA_BODY_KEYS``.
    Kill-check target: add a key to the returned dict without adding it to the
    constant → this fails.
    """
    request = to_openai_request_v2(PromptParts(cacheable=[], non_cacheable=[]), "fa-test-key")

    assert set(request["extra_body"]) == set(COMPOSER_EXTRA_BODY_KEYS)


def test_s10c_no_composer_extra_is_silently_dropped() -> None:
    """C1 (S10c.4 / CT4 / GAP6): every emitted key is recognised, or knowingly excused.

    The gate I-39 asked for. Providers absent from
    ``KNOWN_PROVIDER_PARAMS_KEYS`` (``openai_compat``, ``anthropic``) do
    unrestricted passthrough with no fixed set to validate against, so they are
    skipped — a missing entry means "no check for this provider", not "this
    provider rejects extras".

    **Liveness control:** asserts at least one provider was actually compared.
    An empty registry, a renamed constant or a bad import would otherwise make
    this pass while checking nothing — the failure mode this workstream has hit
    repeatedly.

    Oracle: the set of (provider, key) pairs that are neither recognised nor
    excused is empty.
    Kill-check target: add a fictional key to the composer → fails naming the
    key and adapter. Delete the ``_KNOWN_UNRECOGNISED`` row → also fails,
    proving the row is load-bearing rather than decoration.
    """
    checked = 0
    unexplained: dict[tuple[str, str], str] = {}
    for provider, recognised in KNOWN_PROVIDER_PARAMS_KEYS.items():
        checked += 1
        for key in sorted(COMPOSER_EXTRA_BODY_KEYS):
            if key in recognised:
                continue
            if (provider, key) in _KNOWN_UNRECOGNISED:
                continue
            unexplained[(provider, key)] = (
                f"composer emits {key!r} but the {provider!r} adapter does not recognise it; "
                f"either add it to that adapter's recognised set, stop emitting it for that "
                f"provider, or record it in _KNOWN_UNRECOGNISED with a reason"
            )

    assert checked > 0, (
        "no providers were compared — KNOWN_PROVIDER_PARAMS_KEYS is empty or the import broke, so this gate is inert"
    )
    assert not unexplained, "\n".join(unexplained.values())


def test_s10c_known_unrecognised_entries_are_still_real() -> None:
    """C1 (S10c.4 / CT4): every allow-list row describes a mismatch that still exists.

    An allow-list that outlives its reason is worse than none: it silently
    excuses a key that a later adapter update started recognising, and the next
    reader believes the mismatch is still real. When Mistral does gain
    ``prompt_cache_retention``, this fails and the row must be deleted.

    Oracle: for each row, the provider is in the registry, the key is still
    emitted by the composer, and the adapter still does not recognise it.
    Kill-check target: add the excused key to the adapter's recognised set →
    this fails, telling you to retire the row.
    """
    for (provider, key), reason in _KNOWN_UNRECOGNISED.items():
        assert provider in KNOWN_PROVIDER_PARAMS_KEYS, f"{provider!r} is no longer a checked provider"
        assert key in COMPOSER_EXTRA_BODY_KEYS, f"the composer no longer emits {key!r}; delete this row"
        assert key not in KNOWN_PROVIDER_PARAMS_KEYS[provider], (
            f"{provider!r} now recognises {key!r} — delete this _KNOWN_UNRECOGNISED row. Reason was: {reason}"
        )


def test_s10c_inline_tool_block_is_compact() -> None:
    """C0p (S10c.5 / CT5 / GAP7): the tool block PRODUCTION builds is compact JSON.

    ``indent=2`` inflated this block ~30% for no semantic gain, and it is a
    fixed cost paid on every request — first call at full price, cache hits
    still billed, and context window consumed either way.

    **This test reads the block the composer actually produces.** An earlier
    draft re-encoded the specs locally and compared ``separators`` against
    ``indent=2``; that passed even after production was reverted to
    ``indent=2``, because it never looked at production — a check that cannot
    fail, caught by running the kill-check rather than assuming it worked.

    Oracle (two parts, both required): the emitted block round-trips to the
    same object as the source specs (whitespace-only change), **and** it is
    measurably smaller than the pretty encoding. Size alone would pass on
    truncated output; equality alone would pass on the pretty form.
    Kill-check target: revert ``separators`` to ``indent=2`` in
    ``build_prompt_parts_v2`` → the byte ceiling fails.
    """
    specs = render_tool_specs(build_baseline_registry(Path(tempfile.mkdtemp())).specs())
    parts, _cache_key = build_prompt_parts_v2(
        base_system="sys",
        agents_md_map="",
        tool_defs=[dict(spec) for spec in specs],
        role_id="coder",
    )

    blocks = [m["content"] for m in parts.cacheable if str(m["content"]).startswith("Tools for role")]
    assert len(blocks) == 1, f"expected exactly one tool block, got {len(blocks)}"
    emitted = str(blocks[0]).split("\n", 1)[1]

    assert json.loads(emitted) == json.loads(json.dumps(specs)), "the change must be whitespace-only"

    pretty = json.dumps(specs, indent=2)
    assert len(pretty) - len(emitted) >= 2500, (
        f"the production tool block is not compact: {len(emitted)} bytes vs {len(pretty)} pretty "
        f"(saving {len(pretty) - len(emitted)}, expected >=2500)"
    )
