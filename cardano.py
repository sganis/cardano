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

def get_tip_slot_number():
	cmd  = 'cardano-cli query tip --testnet-magic 1097911063'
	o, e = run(cmd)
	js = json.loads(o)
	return int(js['slotNo'])

def get_ttl():
	return get_tip_slot_number() + 200

def get_key_deposit():
	js = json.loads(open('protocol.json').read())
	return int(js['keyDeposit'])

def get_pool_deposit():
	js = json.loads(open('protocol.json').read())
	return int(js['poolDeposit'])


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


def register(stake_addr_file, stake_skey_file, stake_vkey_file, payment_addr_file, payment_skey_file):
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


def generate_pool_keys():
	cmd = '''cardano-cli node key-gen 
		--cold-verification-key-file cold.vkey 
		--cold-signing-key-file cold.skey 
		--operational-certificate-issue-counter-file cold.counter'''
	run(cmd)
	cmd = '''cardano-cli node key-gen-VRF 
		--verification-key-file vrf.vkey 
		--signing-key-file vrf.skey'''
	run(cmd)
	cmd = '''cardano-cli node key-gen-KES 
		--verification-key-file kes.vkey 
		--signing-key-file kes.skey'''
	run(cmd)
	js = json.loads(open('../relay/testnet-shelley-genesis.json').read())
	slots_per_kes = js['slotsPerKESPeriod']
	print(slots_per_kes)
	slot_no = get_tip_slot_number()
	print(slot_no)
	kes_period = int(slot_no / slots_per_kes)
	print(kes_period)

	cmd = 'cardano-cli node issue-op-cert '
	cmd += '--kes-verification-key-file kes.vkey '
	cmd += '--cold-signing-key-file cold.skey '
	cmd += '--operational-certificate-issue-counter cold.counter '
	cmd += f'--kes-period {kes_period} '
	cmd += '--out-file node.cert'
	run(cmd)


def register_pool():

	payment_addr = open('payment.addr').read()
	payment_skey = open('payment.skey').read()

	cmd ='cardano-cli stake-pool metadata-hash --pool-metadata-file cardano/poolMetadata.json'
	o,e = run(cmd)
	metadata_hash = o.strip()
	pledge = 500 * 1_000_000
	cost = 340 * 1_000_000
	margin = 0.03
	metadata_url = 'https://git.io/JmApG'
	relay_dns = "adapool.chaintrust.com"

	cmd = 'cardano-cli stake-pool registration-certificate '
	cmd += '--cold-verification-key-file cold.vkey '
	cmd += '--vrf-verification-key-file vrf.vkey '
	cmd += f'--pool-pledge {pledge} '
	cmd += f'--pool-cost {cost} '
	cmd += f'--pool-margin {margin} '
	cmd += '--pool-reward-account-verification-key-file stake.vkey '
	cmd += '--pool-owner-stake-verification-key-file stake.vkey '
	cmd += '--testnet-magic 1097911063 '
	cmd += f'--single-host-pool-relay {relay_dns} '
	cmd += '--pool-relay-port 3001 '
	cmd += f'--metadata-url {metadata_url} '
	cmd += f'--metadata-hash {metadata_hash} '
	cmd += '--out-file pool-registration.cert'
	o,e = run(cmd)

	cmd = '''cardano-cli stake-address delegation-certificate 
		--stake-verification-key-file stake.vkey 
		--cold-verification-key-file cold.vkey 
		--out-file delegation.cert'''
	run(cmd)


	get_protocol()
	txhash, txtx, balance = get_tx_hash(payment_addr)

	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {payment_addr}+0 '
	cmd += '--invalid-hereafter 0 --fee 0 --out-file tx.draft '
	cmd += '--certificate-file pool-registration.cert '
	cmd += '--certificate-file delegation.cert'
	run(cmd)

	fee = calculate_min_fee(1, 3)
	print(f'fee: {fee}')
	deposit = get_pool_deposit()
	print(f'deposit: {deposit}')

	change = balance - fee - deposit

	ttl = get_ttl()

	cmd = 'cardano-cli transaction build-raw '
	cmd += f'--tx-in {txhash}#{txtx} '
	cmd += f'--tx-out {payment_addr}+{change} '
	cmd += f'--invalid-hereafter {ttl} '
	cmd += f'--fee {fee} --out-file tx.raw '
	cmd += '--certificate-file pool-registration.cert '
	cmd += '--certificate-file delegation.cert'
	o,e = run(cmd)

	cmd = 'cardano-cli transaction sign --tx-body-file tx.raw '
	cmd += '--signing-key-file payment.skey '
	cmd += '--signing-key-file stake.skey '
	cmd += '--signing-key-file cold.skey '
	cmd += '--out-file tx.signed --testnet-magic 1097911063'
	o,e = run(cmd)

	o,e = run('cardano-cli transaction submit --tx-file tx.signed --testnet-magic 1097911063')
	print(o)
	if e:
		print(f'error: {e}')
	# verify
	# poolId=`cardano-cli stake-pool id --cold-verification-key-file cold.vkey --output-format "hex"`
	# cardano-cli query ledger-state --mary-era --testnet-magic 1097911063 | grep publicKey | grep <poolId>
	
if __name__ == '__main__':
	
	# assert len(sys.argv) > 3  # usage: prog <from> <to> <ada_amount>
	# from_addr = open(sys.argv[1]).read()
	# to_addr = open(sys.argv[2]).read()
	# ada = sys.argv[3]
	# from_skey = sys.argv[1].split('.')[0] + '.skey'
	#send(from_addr, to_addr, ada, from_skey)

	# register stake address
	# payment_addr_file = 'payment.addr'
	# payment_skey_file = payment_addr_file.split('.')[0] + '.skey'
		
	# stake_addr_file = 'stake.addr'
	# stake_skey_file = stake_addr_file.split('.')[0] + '.skey'
	# stake_vkey_file = stake_addr_file.split('.')[0] + '.vkey'

	# register(stake_addr_file, stake_skey_file, stake_vkey_file,
	# 	 payment_addr_file, payment_skey_file)

	# generate stake pool keys
	#generate_pool_keys()

	# register stake pool
	register_pool()