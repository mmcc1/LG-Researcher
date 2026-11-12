from dataclasses import dataclass

from processing.counter_evidence_context_builder import (
    CounterEvidenceContextBuilder,
)


@dataclass
class FakeFinding:

    claim: str


print()
print(
    "COUNTER-EVIDENCE CONTEXT BUILDER TEST"
)
print(
    "====================================="
)


#
# Normal construction.
#

findings = [

    FakeFinding(
        claim=(
            "SHA-256 is used to hash "
            "Bitcoin block headers."
        )
    ),

    FakeFinding(
        claim=(
            "Miners repeatedly modify block "
            "header data while searching for "
            "a valid proof-of-work hash."
        )
    ),

    FakeFinding(
        claim=(
            "Bitcoin nodes validate proof-of-work "
            "by comparing the block hash against "
            "the required target."
        )
    ),
]


builder = (
    CounterEvidenceContextBuilder(
        max_chars=1000,
    )
)


context = builder.build(
    findings
)


print()
print("GENERATED CONTEXT")
print("-----------------")
print(context)


assert (
    "Existing research claims:"
    in context
)

assert (
    "1. SHA-256 is used to hash "
    "Bitcoin block headers."
    in context
)

assert (
    "2. Miners repeatedly modify "
    "block header data"
    in context
)

assert (
    "3. Bitcoin nodes validate "
    "proof-of-work"
    in context
)


#
# Duplicate claims should not be repeated.
#

duplicate_findings = [

    FakeFinding(
        claim="SHA-256 hashes block headers."
    ),

    FakeFinding(
        claim=(
            "  SHA-256   hashes   "
            "block headers. "
        )
    ),

    FakeFinding(
        claim="sha-256 hashes block headers."
    ),
]


duplicate_context = (
    builder.build(
        duplicate_findings
    )
)


print()
print("DEDUPLICATION TEST")
print("------------------")
print(duplicate_context)


assert (
    duplicate_context.count(
        "block headers."
    )
    == 1
)


#
# Empty input.
#

assert builder.build([]) == ""


#
# Blank claims.
#

blank_context = builder.build(
    [
        FakeFinding(
            claim="   "
        ),
        FakeFinding(
            claim="\n\t"
        ),
    ]
)

assert blank_context == ""


#
# Character budget.
#

small_builder = (
    CounterEvidenceContextBuilder(
        max_chars=70,
    )
)


bounded_context = (
    small_builder.build(
        findings
    )
)


print()
print("BOUNDED CONTEXT TEST")
print("--------------------")
print(bounded_context)

print()
print(
    f"Length: "
    f"{len(bounded_context)}"
)


assert (
    len(bounded_context)
    <= 70
)


#
# Invalid configuration.
#

try:

    CounterEvidenceContextBuilder(
        max_chars=0
    )

except ValueError as ex:

    print()
    print(
        f"Expected error: {ex}"
    )

else:

    raise AssertionError(
        "Invalid max_chars was "
        "not rejected."
    )


print()
print(
    "====================================="
)
print("PASS")
print(
    "====================================="
)