from collections import OrderedDict
from utility.printable import Printable


class Transaction(Printable):
    """
        Use the form and concept of transaction, but not with money transfer
    """

    def __init__(self, dataOwner, signature, hop_count):
        """
            self.dataOwner:          your public key
            self.signature:          digital signature
            self.hop_count:          data we want to upload to the blockchain
        """
        self.dataOwner = dataOwner
        self.signature = signature
        self.hop_count = hop_count


    def to_ordered_dict(self):
        """ return as a dictionary """

        return OrderedDict([
            ('dataOwner', self.dataOwner), 
            ('hop_count', self.hop_count)
        ])
