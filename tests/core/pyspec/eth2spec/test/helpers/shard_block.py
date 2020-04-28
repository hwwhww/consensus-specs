from eth2spec.test.helpers.block import get_state_and_beacon_parent_root_at_slot
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
from eth2spec.utils.bls import only_with_bls


@only_with_bls()
def sign_shard_block(spec, beacon_state, shard, block, proposer_index=None):
    slot = block.message.slot
    if proposer_index is None:
        proposer_index = spec.get_shard_proposer_index(beacon_state, slot, shard)

    privkey = privkeys[proposer_index]
    domain = spec.get_domain(beacon_state, spec.DOMAIN_SHARD_PROPOSAL, spec.compute_epoch_at_slot(slot))
    signing_root = spec.compute_signing_root(block.message, domain)
    block.signature = bls.Sign(privkey, signing_root)


def build_shard_block(spec,
                      beacon_state,
                      shard,
                      slot=None,
                      body=None,
                      signed=False):
    shard_state = beacon_state.shard_states[shard]
    if slot is None:
        slot = shard_state.slot + 1

    if body is None:
        body = []

    proposer_index = spec.get_shard_proposer_index(beacon_state, slot, shard)
    beacon_state, beacon_parent_root = get_state_and_beacon_parent_root_at_slot(spec, beacon_state, slot)

    block = spec.ShardBlock(
        shard_parent_root=shard_state.latest_block_root,
        beacon_parent_root=beacon_parent_root,
        slot=slot,
        proposer_index=proposer_index,
        body=body,
    )
    signed_block = spec.SignedShardBlock(
        message=block,
    )

    if signed:
        sign_shard_block(spec, beacon_state, shard, signed_block, proposer_index=proposer_index)

    return signed_block
