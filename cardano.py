#!/usr/bin/env python3
#
# create transaction
import sys
import os
import subprocess
import json

home = os.environ['HOME']
path_to_socket = f"{home}/ada/relay/db/node.socket"


def run(cmd):
	os.environ["CARDANO_NODE_SOCKET_PATH"] = path_to_socket
	cmd = cmd.replace('\n','')
	#print(f'CMD: {cmd}')
	p = subprocess.run(cmd.replace('\n','').split(), capture_output=True)
	stdout = p.stdout.decode().strip()
	stderr = p.stderr.decode().strip()
	return stdout, stderr

def get_protocol():
	cmd = '''cardano-cli query protocol-parameters --mary-era 
			--out-file protocol.json --testnet-magic 1097911063'''
	run(cmd)

def get_tx_hash(addr):
	cmd = f'''cardano-cli query utxo --address {addr}
			--mary-era --testnet-magic 1097911063'''
	o,e = run(cmd)
	# print(o)
	line = o.split('\n')[-1].split()
	# hash, index, balance
	return line[0], line[1], int(line[2])

def calculate_min_fee(tx_out_count, witness_count):
	cmd = 'cardano-cli transaction calculate-min-fee '
	cmd += '--tx-body-file tx.draft --tx-in-count 1 '
	cmd += f'--tx-out-count {tx_out_count} --witness-count {witness_count} '
	cmd += '--byron-witness-count 0 --protocol-params-file protocol.json '
	cmd += f'--testnet-magic 1097911063'
	o,e = run(cmd)
	return int(o.split()[0])

def get_ttl():
	cmd  = 'cardano-cli query tip --testnet-magic 1097911063'
	o, e = run(cmd)
	js = json.loads(o)
	return int(js['slotNo']) + 200

def get_deposit():
	js = json.loads(open('protocol.json').read())
	return int(js['keyDeposit'])


def send(from_addr, to_addr, ada, from_skey):
	print(f'sending {ada} ADA\nFrom: {from_addr}\nTo  : {to_addr}')
	get_protocol()
	txhash, txtx, balance = get_tx_hash(from_addr)
	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {to_addr}+0 '
	cmd += f'--tx-out {from_addr}+0 '
	cmd += '--invalid-hereafter 0 --fee 0 --out-file tx.draft'
	run(cmd)
	lovelaces = int(ada) * 1_000_000
	fee = calculate_min_fee(2, 1)
	ttl = get_ttl()
	change = balance - lovelaces - fee
	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {to_addr}+{lovelaces} '
	cmd += f'--tx-out {from_addr}+{change} '
	cmd += f'--invalid-hereafter {ttl} '
	cmd += f'--fee {fee} --out-file tx.raw'
	o,e = run(cmd)
	print(o)

	cmd = 'cardano-cli transaction sign --tx-body-file tx.raw '
	cmd += f'--signing-key-file {from_skey} --out-file tx.signed --testnet-magic 1097911063'
	o,e = run(cmd)
	
	o,e = run('cardano-cli transaction submit --tx-file tx.signed --testnet-magic 1097911063')
	print(o)
	if e:
		print(f'error: {e}')

	print(get_tx_hash(from_addr))
	print(get_tx_hash(to_addr))


def register(stake_addr_file, stake_skey_file, 
		stake_vkey_file, payment_addr_file, payment_skey_file):
	stake_addr = open(stake_addr_file).read()
	stake_skey = open(stake_addr_file).read()
	payment_addr = open(payment_addr_file).read()
	payment_skey = open(payment_skey_file).read()

	# create certificatge
	cmd = 'cardano-cli stake-address registration-certificate '
	cmd += f'--stake-verification-key-file {stake_vkey_file} --out-file stake.cert'
	o,e = run(cmd)

	get_protocol()
	txhash, txtx, balance = get_tx_hash(payment_addr)
	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {payment_addr}+0 '
	cmd += '--invalid-hereafter 0 --fee 0 --out-file tx.draft '
	cmd += '--certificate-file stake.cert'
	run(cmd)
	fee = calculate_min_fee(1, 2)
	print(f'fee: {fee}')
	deposit = get_deposit()
	print(f'deposit: {deposit}')

	change = balance - fee - deposit

	ttl = get_ttl()

	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {payment_addr}+{change} '
	cmd += f'--invalid-hereafter {ttl} '
	cmd += f'--fee {fee} --out-file tx.raw '
	cmd += '--certificate-file stake.cert'
	o,e = run(cmd)

	cmd = 'cardano-cli transaction sign --tx-body-file tx.raw '
	cmd += f'--signing-key-file {payment_skey_file} '
	cmd += f'--signing-key-file {stake_skey_file} '
	cmd += '--out-file tx.signed --testnet-magic 1097911063'
	o,e = run(cmd)

	o,e = run('cardano-cli transaction submit --tx-file tx.signed --testnet-magic 1097911063')
	print(o)
	if e:
		print(f'error: {e}')

	print(get_tx_hash(payment_addr))

	
if __name__ == '__main__':
	
	# assert len(sys.argv) > 3  # usage: prog <from> <to> <ada_amount>
	# from_addr = open(sys.argv[1]).read()
	# to_addr = open(sys.argv[2]).read()
	# ada = sys.argv[3]
	# from_skey = sys.argv[1].split('.')[0] + '.skey'
	#send(from_addr, to_addr, ada, from_skey)

	# register stake address
	payment_addr_file = 'payment.addr'
	payment_skey_file = payment_addr_file.split('.')[0] + '.skey'
		
	stake_addr_file = 'stake.addr'
	stake_skey_file = stake_addr_file.split('.')[0] + '.skey'
	stake_vkey_file = stake_addr_file.split('.')[0] + '.vkey'

	register(stake_addr_file, stake_skey_file, stake_vkey_file,
		 payment_addr_file, payment_skey_file)

