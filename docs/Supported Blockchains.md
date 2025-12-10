# Supported Blockchains

This document lists the main blockchains and tokens the project supports, grouped by type. It also includes recommended data sources and quick query tips.

## Top Cryptocurrencies (Classic Set)
These are commonly queried via UTXO/block-explorer APIs such as Blockchair or (for Bitcoin) Blockstream.

| Asset Name     | Ticker |
| -------------- | ------:|
| Bitcoin        | BTC    |
| Litecoin       | LTC    |
| Dogecoin       | DOGE   |
| Bitcoin Cash   | BCH    |
| Dash           | DASH   |
| Zcash          | ZEC    |
| Monero         | XMR    |
| Ripple         | XRP    |
| Cardano        | ADA    |
| Stellar        | XLM    |
| EOS            | EOS    |
| TRON           | TRX    |

## EVM & Smart Contract Chains
These networks and their token balances are best queried via an indexer or provider like Moralis, Alchemy, or Infura. Note: Moralis and other providers often reference networks by chain ID rather than ticker.

| Network Name           | Native Token |
| ---------------------- | ------------:|
| Ethereum               | ETH          |
| Polygon                | MATIC (POL)  |
| Binance Smart Chain    | BNB          |
| Solana                 | SOL          |
| Avalanche              | AVAX         |
| Arbitrum               | ETH (gas)    |
| Optimism               | ETH (gas)    |
| Fantom                 | FTM          |
| Cronos                 | CRO          |
| Gnosis                 | xDAI / GNO   |

## Stablecoins (Tokens on ETH / SOL / Polygon / BSC)
Stablecoins live as tokens on underlying chains; query the wallet address on the chain to discover holdings rather than querying a separate "USDC" chain.

| Asset Name  | Ticker |
| ----------- | ------:|
| Tether      | USDT   |
| USD Coin    | USDC   |
| Dai         | DAI    |
| PayPal USD  | PYUSD  |

## Recommended Data Sources

- **Bitcoin & UTXO chains:** Blockchair, Blockstream (BTC-specific), or the chain's native explorers.
- **EVM chains & tokens:** Moralis, Alchemy, Infura, QuickNode — indexer services give token balances and transfers quickly.
- **Solana:** RPC providers (e.g., QuickNode) or Solana-specific indexers.

## Quick Tips for Querying

- For UTXO chains (BTC, LTC, DOGE): use Blockchair or the chain explorer API to fetch transaction history and UTXO sets.
- For EVM-based wallets: query token balances and transfer events via Moralis or an archive node; remember that tokens are discovered by scanning contract events at an address.
- Moralis and some providers use numeric chain IDs (e.g., 1 for Ethereum mainnet). Map the chain ID to the network when building queries.