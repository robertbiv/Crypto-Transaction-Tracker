"""
Wallet linking utility for CSV imports.
Automatically links transaction sources to configured wallets based on name or address.
"""

import json
from typing import Dict, List, Optional, Tuple


class WalletLinker:
    """Links transaction sources to configured wallets."""
    
    def __init__(self, wallet_data: Dict):
        """
        Initialize wallet linker with wallet data.
        
        Args:
            wallet_data: Dictionary with structure {blockchain: {addresses: [...], name: "..."}}
        """
        self.wallet_data = wallet_data
        self._build_address_index()
    
    def _build_address_index(self):
        """Build an index of all addresses for quick lookup."""
        self.address_to_blockchain = {}
        self.address_to_name = {}
        
        for blockchain, data in self.wallet_data.items():
            if isinstance(data, dict):
                name = data.get('name', '')
                for address in data.get('addresses', []):
                    self.address_to_blockchain[address.lower()] = blockchain
                    if name:
                        self.address_to_name[address.lower()] = name
    
    def find_matching_wallet(self, source: str, address: Optional[str] = None) -> Dict:
        """
        Find a matching wallet for a transaction source.
        
        Args:
            source: Source name (exchange or wallet name)
            address: Optional address to match
        
        Returns:
            Dict with keys: blockchain, address, name (if found)
            Empty dict if no match found
        """
        # Try to match by address first
        if address:
            address_lower = address.lower()
            if address_lower in self.address_to_blockchain:
                blockchain = self.address_to_blockchain[address_lower]
                return {
                    'blockchain': blockchain,
                    'address': address,
                    'name': self.address_to_name.get(address_lower, '')
                }
        
        # Try to match by wallet name across all blockchains
        source_lower = source.lower()
        for blockchain, data in self.wallet_data.items():
            if isinstance(data, dict):
                wallet_name = data.get('name', '').lower()
                if wallet_name and wallet_name == source_lower:
                    # Return the first address from this wallet
                    addresses = data.get('addresses', [])
                    if addresses:
                        return {
                            'blockchain': blockchain,
                            'address': addresses[0],
                            'name': data.get('name', '')
                        }
        
        return {}
    
    def get_possible_wallets_for_source(self, source: str) -> List[Dict]:
        """
        Get all possible wallet matches for a source (for user selection).
        
        Args:
            source: Source name
        
        Returns:
            List of wallet matches with blockchain, address, name
        """
        matches = []
        source_lower = source.lower()
        
        # Find exact name matches
        for blockchain, data in self.wallet_data.items():
            if isinstance(data, dict):
                wallet_name = data.get('name', '')
                if wallet_name:
                    if wallet_name.lower() == source_lower:
                        addresses = data.get('addresses', [])
                        for address in addresses:
                            matches.append({
                                'blockchain': blockchain,
                                'address': address,
                                'name': wallet_name,
                                'match_type': 'name'
                            })
        
        # Find partial name matches
        for blockchain, data in self.wallet_data.items():
            if isinstance(data, dict):
                wallet_name = data.get('name', '')
                if wallet_name and source_lower in wallet_name.lower():
                    addresses = data.get('addresses', [])
                    for address in addresses:
                        # Avoid duplicates
                        if not any(m['address'] == address for m in matches):
                            matches.append({
                                'blockchain': blockchain,
                                'address': address,
                                'name': wallet_name,
                                'match_type': 'partial'
                            })
        
        return matches
    
    def get_all_wallets_for_selection(self) -> List[Dict]:
        """
        Get all wallets for user selection during import.
        
        Returns:
            List of all configured wallets with details
        """
        wallets = []
        for blockchain, data in self.wallet_data.items():
            if isinstance(data, dict):
                addresses = data.get('addresses', [])
                name = data.get('name', '')
                
                for idx, address in enumerate(addresses):
                    label = name or f"{blockchain.capitalize()} #{idx + 1}"
                    wallets.append({
                        'blockchain': blockchain,
                        'address': address,
                        'name': name,
                        'label': label,
                        'display': f"{label} ({address[:10]}...)" if len(address) > 10 else label
                    })
        
        return wallets
    
    def enrich_transaction(self, transaction: Dict, wallet_match: Dict) -> Dict:
        """
        Enrich a transaction with wallet information.
        
        Args:
            transaction: Transaction dictionary
            wallet_match: Wallet match from find_matching_wallet()
        
        Returns:
            Updated transaction with wallet_name and wallet_address
        """
        if wallet_match:
            transaction['wallet_name'] = wallet_match.get('name', '')
            transaction['wallet_address'] = wallet_match.get('address', '')
            transaction['wallet_blockchain'] = wallet_match.get('blockchain', '')
        
        return transaction


class WalletMatcher:
    """Matches CSV data to wallets and handles ambiguous cases."""
    
    def __init__(self, wallet_data: Dict):
        """Initialize with wallet data."""
        self.linker = WalletLinker(wallet_data)
    
    def match_transaction_to_wallet(self, transaction: Dict) -> Tuple[Dict, Optional[Dict]]:
        """
        Match a transaction to a wallet.
        
        Args:
            transaction: Transaction with source and optional address
        
        Returns:
            Tuple of (enriched_transaction, ambiguity_info)
            ambiguity_info is None if match is clear, or dict with possible_matches if ambiguous
        """
        source = transaction.get('source', '')
        address = transaction.get('address') or transaction.get('wallet_address')
        
        # Try to find exact match
        wallet_match = self.linker.find_matching_wallet(source, address)
        
        if wallet_match:
            enriched = self.linker.enrich_transaction(transaction.copy(), wallet_match)
            return enriched, None
        
        # Check for possible matches
        possible_matches = self.linker.get_possible_wallets_for_source(source)
        
        if possible_matches:
            # If only one match, use it
            if len(possible_matches) == 1:
                enriched = self.linker.enrich_transaction(transaction.copy(), possible_matches[0])
                return enriched, None
            
            # Multiple matches - ambiguous
            enriched = transaction.copy()
            return enriched, {
                'type': 'ambiguous_wallet',
                'source': source,
                'possible_matches': possible_matches
            }
        
        # No matches found
        return transaction.copy(), None


def load_wallets_and_link(wallet_file: str) -> WalletLinker:
    """Load wallet file and create linker."""
    try:
        with open(wallet_file, 'r') as f:
            wallet_data = json.load(f)
        return WalletLinker(wallet_data)
    except Exception as e:
        raise ValueError(f"Failed to load wallets: {str(e)}")
