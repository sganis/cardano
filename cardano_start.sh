#!/bin/bash
# start cardano node

DIR=$(dirname $(readlink -f $0))
NETOWORK="--testnet-magic 1097911063"
cd $DIR/relay

cardano-node run \
 --topology testnet-topology.json \
 --database-path db \
 --socket-path db/node.socket \
 --host-addr 127.0.0.1 \
 --port 3001 \
 --config testnet-config.json

exit

# from different terminal, query activity
export CARDANO_NODE_SOCKET_PATH=$DIR/relay/db/node.socket
cardano-cli query tip "$NETWORK"

## generate payment key pair
cardano-cli address key-gen \
	--verification-key-file payment.vkey -\
	-signing-key-file payment.skey

## generate a stake key pair
cardano-cli stake-address key-gen \
	--verification-key-file stake.vkey \
	--signing-key-file stake.skey

## generate payment address
cardano-cli address build \
	--payment-verification-key-file payment.vkey \
	--stake-verification-key-file stake.vkey -\
	-out-file payment.addr \
	"$NETWORK"

## grenerate a stake address
cardano-cli stake-address build \
	--stake-verification-key-file stake.vkey \
	--out-file stake.addr $NETWORK

## check balance
cardano-cli query utxo \
	--mary-era --address $(cat payment.addr) $NETWORK

## create a transaction
SRC_BALANCE=20000000
DST_AMOUNT=10000000

# get protocol parameters
cardano-cli query protocol-parameters --out-file protocol.json "$NETWORK" 

# get hash and index for --tx-in <TxHash>#<TxTx>
cardano-cli query utxo --address $(cat payment.addr) "$NETWORK"

# draft tx
cardano-cli transaction build-raw \
--tx-in 4e3a6e7fdcb0d0efa17bf79c13aed2b4cb9baf37fb1aa2e39553d5bd720c5c99#4 \
--tx-out $(cat payment2.addr)+0 \
--tx-out $(cat payment.addr)+0 \
--invalid-hereafter 0 \
--fee 0 \
--out-file tx.draft

# calculate fee
FEE=$(cardano-cli transaction calculate-min-fee \
	--tx-body-file tx.draft \
	--tx-in-count 1 \
	--tx-out-count 2 \
	--witness-count 1 \
	--byron-witness-count 0 \
	"$NETWORK" \
	--protocol-params-file protocol.json)
# calculate change
CHANGE=$(expr $SRC_BALANCE - $DST_AMOUNT - $FEE)

# set TTL, get slotNo from this
cardano-cli query tip "$NETWORK"
#TTL=slotNo+200

# build tx
cardano-cli transaction build-raw \
	--tx-in 4e3a6e7fdcb0d0efa17bf79c13aed2b4cb9baf37fb1aa2e39553d5bd720c5c99#4 \
	--tx-out $(cat payment2.addr)+$DST_AMOUNT \
	--tx-out $(cat payment.addr)+$CHANGE \
	--invalid-hereafter $TTL \
	--fee $FEE \
	--out-file tx.raw

# sign tx
cardano-cli transaction sign \
	--tx-body-file tx.raw \
	--signing-key-file payment.skey \
	"$NETWORK" \
	--out-file tx.signed

# submit tx
cardano-cli transaction submit \
	--tx-file tx.signed \
	"$NETWORK"

# check balances
cardano-cli query utxo \
    --address $(cat payment.addr) \
    "$NETWORK"
cardano-cli query utxo \
    --address $(cat payment2.addr) \
    "$NETWORK"

