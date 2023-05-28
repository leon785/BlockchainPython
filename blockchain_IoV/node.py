from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import time
import datetime

from wallet import Wallet
from blockchain import Blockchain

app = Flask(__name__)
CORS(app)
read_from = 0
port = -1
loop_count = 0

# ui 
@app.route('/', methods=['GET'])
def get_node_ui():
    return send_from_directory('ui', 'node.html')


@app.route('/network', methods=['GET'])
def get_network_ui():
    return send_from_directory('ui', 'network.html')



# transaction and chain
@app.route('/transactions', methods=['GET'])
def get_open_transaction():
    transactions = blockchain.get_open_transactions()
    dict_transactions = [tx.__dict__ for tx in transactions]
    return jsonify(dict_transactions), 200


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_snapshot = blockchain.chain
    dict_chain = [block.__dict__.copy() for block in chain_snapshot]
    for dict_block in dict_chain:
        dict_block['transactions'] = [tx.__dict__ for tx in dict_block['transactions']]
    return jsonify(dict_chain), 200



# nodes
@app.route('/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data attached.'
        }
        return jsonify(response), 400
    if 'node' not in values:
        response = {
            'message': 'No node data found.'
        }
        return jsonify(response), 400
    node = values['node']
    blockchain.add_peer_node(node)
    response = {
        'message': 'Node added successfully.',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 201


@app.route('/node/<node_url>', methods=['DELETE'])
def remove_node(node_url):
    if node_url == '' or node_url == None:
        response = {
            'message': 'No node found.'
        }
        return jsonify(response), 400
    blockchain.remove_peer_node(node_url)
    response = {
        'message': 'Successfullt removed node.',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 200


@app.route('/nodes', methods=['GET'])
def get_nodes():
    response = {
        'message': 'Successfully get nodes',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 200



# keys
@app.route('/wallet', methods=['POST'])
def create_keys():
    wallet.create_keys()
    if wallet.save_keys():
        global blockchain
        blockchain = Blockchain(wallet.public_key, port)
        response = {
            'message': 'Keys created successfully',
            'public_key': wallet.public_key,
            'private_key': wallet.private_key
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Saving the keys failed.'
        }
        return jsonify(response), 500


@app.route('/wallet', methods=['GET'])
def load_keys():
    if wallet.load_keys():
        global blockchain
        blockchain = Blockchain(wallet.public_key, port)
        response = {
            'message': 'Keys loaded successfully',
            'public_key': wallet.public_key,
            'private_key': wallet.private_key
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Loading the keys failed.'
        }
        return jsonify(response), 500



# broadcast
@app.route('/broadcast-transaction', methods=['POST'])
def broadcast_transaction():
    values = request.get_json()

    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    required = ['dataOwner', 'signature', 'hop_count']
    if not all(key in values for key in required):
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400

    success = blockchain.add_transaction(
        values['dataOwner'], 
        values['signature'], 
        values['hop_count'], 
        is_receiving=True)
    if success:
        response = {
            'message': 'Successfully added transaction.',
            'transaction': {
                'dataOwner': values['dataOwner'],
                'signature': values['signature'],
                'hop_count': values['hop_count']
            }
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a transaction failed.'
        }
        return jsonify(response), 500


@app.route('/broadcast-block', methods=['POST'])
def broadcast_block():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    if 'block' not in values:
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    block = values['block']
    if block['index'] == blockchain.chain[-1].index + 1:
        if blockchain.add_block(block):
            response = {'message': 'Successflly added block'}
            return jsonify(response), 201
        else:
            response = {'message': 'Block seems invalid.'}
            return jsonify(response), 409
    elif block['index'] > blockchain.chain[-1].index:
        response = {'message': 'Blockchain seems to differ from local blockchain.'}
        blockchain.resolve_conflicts = True
        return jsonify(response), 200
    else: 
        response = {'message': 'Blockchain seems to be shorter, block not added'}
        return jsonify(response), 409



@app.route('/transaction', methods=['POST'])
def add_transaction():
    if wallet.public_key == None:
        response = {
            'message': 'No wallet set up.'
        }
        return jsonify(response), 400
    
    values = request.get_json()

    if not values:
        response = {
            'message': 'No data found.'
        }
        return jsonify(response), 400
    
    required_fields = ['hop_count']
    if not all(field in values for field in required_fields):
        response = {
            'message': 'Required data is missing.'
        }
        return jsonify(response), 400
    
    data_hopCount = values['hop_count']
    signature = wallet.sign_transaction(wallet.public_key, data_hopCount)

    success = blockchain.add_transaction(wallet.public_key, signature, data_hopCount)

    if success:
        response = {
            'message': 'Successfully added transaction.',
            'transaction': {
                'dataOwner': wallet.public_key,
                'signature': signature,
                'hop_count': data_hopCount
            }
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a transaction failed.'
        }
        return jsonify(response), 500


@app.route('/mine', methods=['POST'])
def mine():
    if blockchain.resolve_conflicts:
        response = {'message': 'Resolve conflicts first, block not added!'}
        return jsonify(response), 409
    block = blockchain.mine_block()

    if block is not None:
        dict_block = block.__dict__.copy()

        dict_block['transactions'] = [tx.__dict__ for tx in dict_block['transactions']]

        response = {
            'message': 'Block added successfully.',
            'block': dict_block
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Adding a block failed.',
            'wallet_set_up': wallet.public_key != None
        }
        return jsonify(response), 500


@app.route('/resolve-conflicts', methods=['POST'])
def resolve_conflicts():
    replaced = blockchain.resolve()
    if replaced:
        response = {'message': 'Chain was replaced!'}
    else:
        response = {'message': 'Local chain kept!'}
    return jsonify(response), 200



# local file check
@app.route('/file-check', methods=['POST'])
def timed_check():
    global read_from, port, loop_count
    print('port is ', port)
    file_directory = "../tictocSimulation/dataOutput/dataTxc15.txt"

    while loop_count <= 100:
        try:
            with open(file_directory, mode='r') as f:
                file_content = f.readlines()[read_from:]
                read_from += len(file_content)
                print('Pointer is at: ', read_from)

                if len(file_content) != 0:
                    for row in file_content:
                        print('looping ... ', datetime.datetime.now(), ' ...')
                        if add_tx_backend(row):
                            print('Successfully added tx from backend at ', datetime.datetime.now())
                        else:
                            print('Error occurred in add_tx_backend')
                            break
                    print('Out of loop')
                    mine_backend()
                    print('======= MINED A BLOCK SUCCESSFULLY =======')
                    print('======= ', datetime.datetime.now(), ' =======')
        except (IOError, IndexError):
            print("An error occurred during time_check !!")
            return False

        time.sleep(1) 
        loop_count += 1
        print('IT\'S LOOP ', loop_count, 'RN')
    
    response = {
        'message': 'Successfully get checked'
    }
    return jsonify(response), 200


def add_tx_backend(hop_count):
    if wallet.public_key == None or hop_count == None:
        return False
    signature = wallet.sign_transaction(wallet.public_key, hop_count)
    success = blockchain.add_transaction(wallet.public_key, signature, hop_count)
    if success:
        return True
    return False


def mine_backend():
    try:
        blockchain.mine_block()
    except TypeError or TimeoutError:
        raise Exception("An error occurred when calling mine_backend !!")


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    wallet = Wallet(port)
    blockchain = Blockchain(wallet.public_key, port)
    app.run(host='0.0.0.0', port=port)

