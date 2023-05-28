from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import Crypto.Random
import binascii
from tinydb import TinyDB, Query


class Wallet:
    """ An account for user to play with transaction """

    def __init__(self, node_id):
        """
            self.private_key:       private key
            self.public_key:        public key
            self.node_id:           your current port
        """
        
        self.private_key = None
        self.public_key = None
        self.node_id = node_id


    def generate_keys(self):
        private_key = RSA.generate(1024, Crypto.Random.new().read)
        public_key = private_key.publickey()
        return (binascii.hexlify(private_key.exportKey(format='DER')).decode('ascii'), 
                binascii.hexlify(public_key.exportKey(format='DER')).decode('ascii'))


    def create_keys(self):
        private_key, public_key = self.generate_keys()
        self.private_key = private_key
        self.public_key = public_key


    def save_keys(self):
        if self.public_key != None and self.private_key != None:
            try:
                db = TinyDB('./db/wallet-{}.json'.format(self.node_id))
                db.truncate()
                db.insert({"public_key": self.public_key, 
                           "private_key": self.private_key})
                return True
            except (IOError, IndexError):
                print('Saving wallet FAILED')
                return False


    def load_keys(self):
        try:
            db = TinyDB('./db/wallet-{}.json'.format(self.node_id))
            all_pairs = db.all()
            # Currently we just choose the last pair, can be improved in the future
            last_pair = all_pairs[0]
            self.public_key = last_pair['public_key']
            self.private_key = last_pair['private_key']
            return True
        except (IOError, IndexError):
            print('Loading wallet FAILED')
            return False


    def sign_transaction(self, dataOwner, hop_count):
        """
            Sign a transaction and return the signature

            dataOwner:          your public key
            hop_count:          data we want to upload to the blockchain
        """

        signer = PKCS1_v1_5.new(RSA.importKey(binascii.unhexlify(self.private_key)))
        h = SHA256.new((str(dataOwner) + str(hop_count)).encode('utf8'))
        signature = signer.sign(h)
        return binascii.hexlify(signature).decode('ascii')


    @staticmethod
    def verify_transaction(transaction):
        """
            Verify the signature of a transaction.
        """
        
        public_key = RSA.importKey(binascii.unhexlify(transaction.dataOwner))
        verifier = PKCS1_v1_5.new(public_key)
        h = SHA256.new((str(transaction.dataOwner) + str(transaction.hop_count)).encode('utf8'))
        return verifier.verify(h, binascii.unhexlify(transaction.signature))