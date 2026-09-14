from eth_utils import keccak

from salvage.tools.airdrops import build_tree, leaf_hash, verify_proof


def test_leaf_hash_matches_solidity_packed_encoding():
    account = "0x" + "11" * 20
    expected = keccak((7).to_bytes(32, "big") + bytes.fromhex("11" * 20) + (1000).to_bytes(32, "big"))
    assert leaf_hash(7, account, 1000) == expected


def test_every_entry_verifies_against_the_root():
    entries = [(i, "0x" + f"{i + 1:040x}", (i + 1) * 10**6) for i in range(11)]  # odd count on purpose
    root, proofs = build_tree(entries)
    for i, account, amount in entries:
        p = proofs[account.lower()]
        assert p["index"] == i and p["amount"] == amount
        assert verify_proof(root, i, account, amount, p["proof"])


def test_wrong_amount_does_not_verify():
    entries = [(0, "0x" + "aa" * 20, 5), (1, "0x" + "bb" * 20, 6)]
    root, proofs = build_tree(entries)
    p = proofs["0x" + "aa" * 20]
    assert not verify_proof(root, 0, "0x" + "aa" * 20, 999, p["proof"])
