from functools import reduce
import hashlib as hl
import json
import pickle
import requests
from tinydb import TinyDB, Query

from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from transaction import Transaction
from wallet import Wallet

# print(__name__)


class Blockchain:
    """
        Basic blockchain

        genesis_block:              the first block for all the blockchains
        self.__chain:               blockchain
        self.__open_transactions:   the transactions that still waiting for writing into the blockchain
        self.__peer_nodes:          nodes that can interact with
    """

    def __init__(self, public_key, node_id):
        # the first block in the chain
        genesis_block = Block(0, '', [], 100, 0)
        # blockchain
        self.__chain = [genesis_block]
        # pending
        self.__open_transactions = []
        # peer nodes
        self.__peer_nodes = set()

        # load blockchain
        self.public_key = public_key
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()


    # blockchain: get / set
    @property
    def chain(self):
        return self.__chain[:]

    @chain.setter
    def chain(self, val):
        self.__chain = val

    
    # open transaction: get
    def get_open_transactions(self):
        return self.__open_transactions[:]
    

    # peer node: add / remove / get
    def add_peer_node(self, node):
        self.__peer_nodes.add(node)
        self.save_data(save_nodes=True)

    def remove_peer_node(self, node):
        self.__peer_nodes.discard(node)
        self.save_data(save_nodes=True)

    def get_peer_nodes(self):
        return list(self.__peer_nodes)


    def save_data(self, save_chain=False, save_opentx=False, save_nodes=False) :
        try:
            if save_chain:
                db_blockchain = TinyDB('./db/blockchain-{}.json'.format(self.node_id))
                saveable_chain = [block.__dict__ for block in [
                    Block(block.index, 
                            block.previous_hash, 
                            [tx.__dict__ for tx in block.transactions], 
                            block.proof, 
                            block.timestamp) 
                for block in self.__chain]]
                db_blockchain.truncate()
                for block in saveable_chain:
                    db_blockchain.insert(block)

            if save_opentx:
                db_opentx = TinyDB('./db/opentx-{}.json'.format(self.node_id))
                saveable_tx = [tx.__dict__ for tx in self.__open_transactions]
                db_opentx.truncate()
                for tx in saveable_tx:
                    db_opentx.insert(tx)

            if save_nodes:
                db_nodes = TinyDB('./db/peernodes-{}.json'.format(self.node_id))
                saveable_nodes = [{"node": node} for node in list(self.__peer_nodes)]
                db_nodes.truncate()
                for node in saveable_nodes:
                    db_nodes.insert(node)

        except IOError:
            print('Saving data FAILED')


    def load_data(self):
        try: 
            db_blockchain = TinyDB('./db/blockchain-{}.json'.format(self.node_id))
            db_opentx = TinyDB('./db/opentx-{}.json'.format(self.node_id))
            db_nodes = TinyDB('./db/peernodes-{}.json'.format(self.node_id))

            blockchain = db_blockchain.all()
            open_transactions = db_opentx.all()
            peer_nodes = db_nodes.all()

            # save default value (genesis block in this case)
            if len(blockchain) is not 0:
                self.__chain = [Block(
                    block['index'],
                    block['previous_hash'],
                    [Transaction(
                        tx['dataOwner'], 
                        tx['signature'], 
                        tx['hop_count']
                    ) for tx in block['transactions']],
                    block['proof'],
                    block['timestamp']
                ) for block in blockchain]

            # save default value
            if len(open_transactions) is not 0:
                self.__open_transactions = [Transaction(
                    tx['dataOwner'], 
                    tx['signature'], 
                    tx['hop_count']
                ) for tx in open_transactions]

            # save default value
            if len(peer_nodes) is not 0:
                self.__peer_nodes = set([node['node'] for node in peer_nodes])

        except (IOError, IndexError):
            pass


    def proof_of_work(self):
        """ to get a string starts with 00 """
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0

        while not Verification.valid_proof(self.__open_transactions, last_hash, proof):
            proof += 1
        return proof


    def add_transaction(self, dataOwner, signature, hop_count, is_receiving=False):
        """ 
            Append the transaction to the open_transaction list

            dataOwner:              your public key
            signature:              digital signature
            hop_count:              data we need to upload
            is_receiving:           check if this calling is a broadcast from other nodes
        """

        transaction = Transaction(dataOwner, signature, hop_count)
        if Verification.verify_transaction(transaction):
            self.__open_transactions.append(transaction)
            self.save_data(save_opentx=True)

            # Broadcasting
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url, json={
                            'dataOwner': dataOwner, 
                            'signature': signature,
                            'hop_count': hop_count
                        })
                        if response.status_code == 400 or response.status_code == 500:
                            print('Transaction declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        print('Error occurred when Broadcasting Transaction')
                        continue
            return True
        return False


    def mine_block(self):
        """ 
            Add a new block to the current chain,
            The tx in open_transaction will be added to this block
        """

        if self.public_key == None:
            return None

        hashed_block = hash_block(self.__chain[-1])
        proof = self.proof_of_work()
        copied_transactions = self.__open_transactions[:]
        for tx in copied_transactions:
            if not Wallet.verify_transaction(tx):
                return None
        
        block = Block(len(self.__chain), hashed_block, copied_transactions, proof)
        self.__chain.append(block)
        self.__open_transactions = []
        self.save_data(save_chain=True, save_opentx=True)

        # Broadcasting
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [tx.__dict__ for tx in converted_block['transactions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                print('Error occurred when Broadcasting Block')
                continue
        return block


    def add_block(self, block):
        """ Create a new block, used for broadcasting"""

        transactions = [Transaction(
            tx['dataOwner'], 
            tx['signature'], 
            tx['hop_count']
        ) for tx in block['transactions']]

        proof_is_valid = Verification.valid_proof(transactions, block['previous_hash'], block['proof'])
        hashes_match = hash_block(self.__chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        
        converted_block = Block(block['index'], 
                                block['previous_hash'], 
                                transactions, 
                                block['proof'], 
                                block['timestamp']
        )
        self.__chain.append(converted_block)
        stored_transactions = self.__open_transactions[:]

        # check the open transaction when broadcasting
        for itx in block['transactions']:
            for opentx in stored_transactions:
                if opentx.dataOwner == itx['dataOwner'] and opentx.signature == itx['signature'] and opentx.hop_count == itx['hop_count']:
                    try:
                        self.__open_transactions.remove(opentx)
                    except ValueError:
                        print('Opentx not found, maybe it is already removed')
        self.save_data(save_chain=True, save_opentx=True)
        return True
    

    def resolve(self):
        """ resolve the blockchain conflicts, the longer one wins """

        winner_chain = self.__chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                response = requests.get(url)
                node_chain = response.json()
                node_chain = [Block(
                    block['index'], 
                    block['previous_hash'], 
                    [Transaction(
                        tx['dataOwner'], 
                        tx['signature'], 
                        tx['hop_count']
                    ) for tx in block['transactions']],
                    block['proof'],
                    block['timestamp']
                ) for block in node_chain]

                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)

                # replace the BC if the received one is longer
                if node_chain_length > local_chain_length and Verification.verify_chain(node_chain):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.__chain = winner_chain
        if replace:
            self.__open_transactions = []
        self.save_data(save_chain=True, save_opentx=True)
        return replace



