// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
}

/// @title MerkleAirdrop
/// @notice A standard merkle distributor: eligible (index, account, amount) leaves, one claim per index,
///         and a deadline after which the window is closed. Deployed on the fork to represent an
///         airdrop that a wallet is eligible for but has never claimed.
contract MerkleAirdrop {
    address public immutable token;
    bytes32 public immutable merkleRoot;
    uint256 public immutable deadline;

    mapping(uint256 => uint256) private claimedBitMap;

    event Claimed(uint256 index, address account, uint256 amount);

    error WindowClosed();
    error AlreadyClaimed();
    error InvalidProof();
    error TransferFailed();

    constructor(address token_, bytes32 merkleRoot_, uint256 deadline_) {
        token = token_;
        merkleRoot = merkleRoot_;
        deadline = deadline_;
    }

    function isClaimed(uint256 index) public view returns (bool) {
        uint256 wordIndex = index / 256;
        uint256 bitIndex = index % 256;
        uint256 word = claimedBitMap[wordIndex];
        uint256 mask = (1 << bitIndex);
        return word & mask == mask;
    }

    function _setClaimed(uint256 index) private {
        uint256 wordIndex = index / 256;
        uint256 bitIndex = index % 256;
        claimedBitMap[wordIndex] = claimedBitMap[wordIndex] | (1 << bitIndex);
    }

    function claim(uint256 index, address account, uint256 amount, bytes32[] calldata proof) external {
        if (block.timestamp > deadline) revert WindowClosed();
        if (isClaimed(index)) revert AlreadyClaimed();

        bytes32 node = keccak256(abi.encodePacked(index, account, amount));
        if (!_verify(proof, merkleRoot, node)) revert InvalidProof();

        _setClaimed(index);
        if (!IERC20(token).transfer(account, amount)) revert TransferFailed();
        emit Claimed(index, account, amount);
    }

    function _verify(bytes32[] calldata proof, bytes32 root, bytes32 leaf) private pure returns (bool) {
        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 p = proof[i];
            if (computed <= p) {
                computed = keccak256(abi.encodePacked(computed, p));
            } else {
                computed = keccak256(abi.encodePacked(p, computed));
            }
        }
        return computed == root;
    }
}
