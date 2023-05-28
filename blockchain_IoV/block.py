from time import time
from utility.printable import Printable


class Block(Printable):
    """
        Basic block for blockchain
    """
    
    def __init__(self, index, previous_hash, transactions, proof, time=time()):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.proof = proof
        self.timestamp = time


