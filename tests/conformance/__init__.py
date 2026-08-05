"""S13.5 conformance harness (offline).

The offline half is the CI ratchet: it drives FA's REAL composer
(``build_prompt_parts_v2``) through the REAL production validator
(``fa.providers.message_rules.validate_message_order``) and records a
capability matrix for CONF-1..7. Every case carries a positive control
(ran == True) so a green cell can never come from "never ran" (D5a rule 1).
"""
