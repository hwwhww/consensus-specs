from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.block import get_state_and_beacon_parent_root_at_slot
from eth2spec.test.helpers.state import next_slots
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
        body = b'\x56' * 128

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


def build_shard_transitions_till_slot(spec, state, shards, shard_blocks, target_len_offset_slot):
    state = state.copy()
    next_slots(spec, state, target_len_offset_slot)
    shard_transitions = [spec.ShardTransition()] * spec.MAX_SHARDS
    for shard in shards:
        offset_slots = spec.get_offset_slots(state, shard)
        len_offset_slots = len(offset_slots)
        assert len_offset_slots == target_len_offset_slot
        shard_blocks_of_shard = shard_blocks[shard]
        shard_transition = spec.get_shard_transition(state, shard, shard_blocks_of_shard)
        shard_block_root = shard_blocks_of_shard[-1].message.hash_tree_root()

        assert shard_transition.shard_states[len_offset_slots - 1].latest_block_root == shard_block_root
        assert shard_transition.shard_states[len_offset_slots - 1].slot == offset_slots[-1]
        shard_transitions[shard] = shard_transition

    return shard_transitions


def build_attestation_with_shard_transition(spec, state, slot, index, shard_transition):
    state = state.copy()
    target_offset_slots = len(shard_transition.shard_states)
    next_slots(spec, state, target_offset_slots)
    attestation = get_valid_on_time_attestation(
        spec,
        state,
        slot=slot,
        index=index,
        shard_transition=shard_transition,
        signed=True,
    )
    assert attestation.data.slot == slot
    assert attestation.data.shard_transition_root == shard_transition.hash_tree_root()
    return attestation
