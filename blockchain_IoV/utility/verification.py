from utility.hash_util import hash_string_256, hash_block
from wallet import Wallet


class Verification:
    """A class of verification functions"""

    @staticmethod
    def valid_proof(transactions, last_hash, proof):
        """
            Validate a proof of work number and see if it solves the puzzle algorithm

            transactions:      The transactions of the current block
            last_hash:         Previous block's hash 
            proof:             The proof number
        """

        guess = (str([tx.to_ordered_dict() for tx in transactions]) + str(last_hash) + str(proof)).encode()
        guess_hash = hash_string_256(guess)
        return guess_hash[0:3] == '000'


    @classmethod
    def verify_chain(cls, blockchain):
        """ Verify by checking the hash """
        for (index, block) in enumerate(blockchain):
            if index == 0:
                continue
            if block.previous_hash != hash_block(blockchain[index - 1]):
                print('previousHashErr')
                return False
            if not cls.valid_proof(block.transactions, block.previous_hash, block.proof):
                print('Proof of work is invalid')
                return False
        return True


    @staticmethod
    def verify_transaction(transaction, check_upload=True):
        """
            Check that the upload is not empty and transaction is valid
        """

        if check_upload:
            return transaction.hop_count != None and Wallet.verify_transaction(transaction)
        else:
            return Wallet.verify_transaction(transaction)


    @classmethod
    def verify_transactions(cls, open_transactions, get_balance):
        return all([cls.verify_transaction(tx, get_balance, False) for tx in open_transactions])