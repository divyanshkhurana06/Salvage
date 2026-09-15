"""Per chain addresses and the minimal ABIs Salvage needs.

Everything here is read against local Anvil forks of the real chains, so the addresses
are the real ones. Two chains are wired: Ethereum mainnet and Base. Adding a chain is one
entry in CHAINS (position manager, tokens with their Chainlink USD feeds) plus a fork.
"""

from __future__ import annotations

MAX_UINT128 = (1 << 128) - 1

# chain name -> everything Salvage needs to read it. tokens: symbol -> (token address, Chainlink USD feed)
CHAINS: dict[str, dict] = {
    "ethereum": {
        "label": "Ethereum",
        "chain_id": 1,
        "tip_wei": 1_000_000_000,  # a typical priority fee, added to the block base fee for gas estimates
        "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
        "tokens": {
            "WETH": ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"),
            "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6"),
            "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "0x3E7d1eAB13ad0104d2750B8863b489D65364e32D"),
            "DAI": ("0x6B175474E89094C44Da98b954EedeAC495271d0F", "0xAed0c38402a5d19df6E4c03F4E2DceD6e29c1ee9"),
            "WBTC": ("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", "0x4a3411ac2948B33c69666B35cc6d055B27Ea84f1"),  # BTC/USD aggregator, used for WBTC
        },
    },
    "base": {
        "label": "Base",
        "chain_id": 8453,
        "tip_wei": 1_000_000,  # Base priority fees are a thousandth of Ethereum's
        "position_manager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
        "tokens": {
            "WETH": ("0x4200000000000000000000000000000000000006", "0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70"),
            "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "0x7e860098F58bBFC8648a4311b374B1D669a2bc6B"),
            "USDbC": ("0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA", "0x7e860098F58bBFC8648a4311b374B1D669a2bc6B"),  # bridged USDC, priced with the USDC feed
            "DAI": ("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb", "0x591e79239a7d679378eC8c847e5038150364C78F"),
            "cbBTC": ("0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf", "0x07DA0E54543a844a80ABE69c8A12F22B3aA59f9D"),
            "cbETH": ("0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22", "0xd7818272B9e248357d13057AAb0B417aF31E817d"),
        },
    },
}

# the assets a market shock moves: the token symbols that track ETH and BTC on any chain
SHOCK_SYMBOLS = ("WETH", "cbETH", "WBTC", "cbBTC")

# Ethereum aliases, kept for the scripts that build the wallet set and the airdrops there
NONFUNGIBLE_POSITION_MANAGER = CHAINS["ethereum"]["position_manager"]
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
PRICED_TOKENS: dict[str, tuple[str, str]] = CHAINS["ethereum"]["tokens"]
TOKEN_TO_FEED: dict[str, str] = {addr.lower(): feed for addr, feed in PRICED_TOKENS.values()}
TOKEN_TO_SYMBOL: dict[str, str] = {addr.lower(): sym for sym, (addr, _) in PRICED_TOKENS.items()}

ERC20_ABI = [
    {"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "string"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint8"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"name": "a", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "transfer", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]},
]

CHAINLINK_ABI = [
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint8"}]},
    {
        "name": "latestRoundData", "type": "function", "stateMutability": "view", "inputs": [],
        "outputs": [
            {"name": "roundId", "type": "uint80"}, {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"}, {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"},
        ],
    },
]

POSITION_MANAGER_ABI = [
    {"name": "totalSupply", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "tokenByIndex", "type": "function", "stateMutability": "view", "inputs": [{"name": "index", "type": "uint256"}], "outputs": [{"type": "uint256"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"name": "owner", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "tokenOfOwnerByIndex", "type": "function", "stateMutability": "view", "inputs": [{"name": "owner", "type": "address"}, {"name": "index", "type": "uint256"}], "outputs": [{"type": "uint256"}]},
    {"name": "ownerOf", "type": "function", "stateMutability": "view", "inputs": [{"name": "tokenId", "type": "uint256"}], "outputs": [{"type": "address"}]},
    {
        "name": "positions", "type": "function", "stateMutability": "view",
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "outputs": [
            {"name": "nonce", "type": "uint96"}, {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"}, {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"}, {"name": "tickLower", "type": "int24"}, {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"}, {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"}, {"name": "tokensOwed1", "type": "uint128"},
        ],
    },
    {
        "name": "collect", "type": "function", "stateMutability": "payable",
        "inputs": [{
            "name": "params", "type": "tuple",
            "components": [
                {"name": "tokenId", "type": "uint256"}, {"name": "recipient", "type": "address"},
                {"name": "amount0Max", "type": "uint128"}, {"name": "amount1Max", "type": "uint128"},
            ],
        }],
        "outputs": [{"name": "amount0", "type": "uint256"}, {"name": "amount1", "type": "uint256"}],
    },
]

MERKLE_AIRDROP_ABI = [
    {"name": "token", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "merkleRoot", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "bytes32"}]},
    {"name": "deadline", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "isClaimed", "type": "function", "stateMutability": "view", "inputs": [{"name": "index", "type": "uint256"}], "outputs": [{"type": "bool"}]},
    {
        "name": "claim", "type": "function", "stateMutability": "nonpayable",
        "inputs": [
            {"name": "index", "type": "uint256"}, {"name": "account", "type": "address"},
            {"name": "amount", "type": "uint256"}, {"name": "proof", "type": "bytes32[]"},
        ],
        "outputs": [],
    },
]
