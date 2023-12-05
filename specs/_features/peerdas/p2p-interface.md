# Peer Data Availability Sampling -- Networking

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in PeerDAS](#modifications-in-peerdas)
  - [Preset](#preset)
  - [Containers](#containers)
    - [`DataColumnSidecar`](#datacolumnsidecar)
    - [`DataColumnIdentifier`](#datacolumnidentifier)
  - [Helpers](#helpers)
      - [`verify_column_sidecar`](#verify_column_sidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Samples subnets](#samples-subnets)
        - [`data_column_sidecar_{subnet_id}`](#data_column_sidecar_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [DataColumnSidecarByRoot v1](#datacolumnsidecarbyroot-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in PeerDAS

### Preset

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `KZG_COMMITMENTS_MERKLE_PROOF_INDEX`   | `uint64(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'))` (= 27) | <!-- predefined --> Merkle proof index for `blob_kzg_commitments` |

### Containers

#### `DataColumnSidecar`

```python
class DataColumnSidecar(Container):
    index: LineIndex  # Index of column in extended matrix
    column: DataColumn
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitment_merkle_proof: Vector[Bytes32, KZG_COMMITMENT_INCLUSION_PROOF_DEPTH]
```

#### `DataColumnIdentifier`

```python
class DataColumnIdentifier(Container):
    block_root: Root
    index: LineIndex
```

### Helpers

##### `verify_sample_proof_batch`

```python
def verify_sample_proof_batch(
        row_commitments: Sequence[KZGCommitment],
        row_ids: Sequence[LineIndex],
        column_ids: Sequence[LineIndex],
        datas: Sequence[Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]],
        proofs: Sequence[KZGProof]) -> bool:
    """
    Defined in polynomial-commitments-sampling.md
    """
    ...
```

##### `verify_column_sidecar`

```python
def verify_column_sidecar(sidecar: DataColumnSidecar) -> bool:
    column = sidecar.column
    cell_count = len(column) // FIELD_ELEMENTS_PER_CELL
    cells = [column[i * FIELD_ELEMENTS_PER_CELL:(i + 1) * FIELD_ELEMENTS_PER_CELL] for i in range(cell_count)]

    assert len(cells) == len(sidecar.kzg_commitments) == len(sidecar.kzg_proofs)
    # KZG batch verify the cells match the corresponding commitments and proofs
    assert verify_sample_proof_batch(
        row_commitments=sidecar.kzg_commitments,
        row_ids=list(range(sidecar.column)),  # all rows
        column_ids=[sidecar.index],
        datas=cells,
        proofs=sidecar.kzg_proofs
    )
    # Verify if it's included in the beacon block
    return is_valid_merkle_branch(
        leaf=hash_tree_root(sidecar.kzg_commitments),
        branch=sidecar.kzg_commitments_merkle_proof,
        depth=floorlog2(KZG_COMMITMENTS_MERKLE_PROOF_INDEX),
        index=KZG_COMMITMENTS_MERKLE_PROOF_INDEX,
        root=sidecar.signed_block_header.message.body_root,
    )
```

TODO: define `verify_cells` helper.

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Pe to support upgraded types.

#### Topics and messages

##### Samples subnets

###### `data_column_sidecar_{subnet_id}`

This topic is used to propagate column sidecars, where each column maps to some `subnet_id`.

The *type* of the payload of this topic is `DataColumn`.

TODO: add verification rules. Verify with `verify_column_sidecar`.

### The Req/Resp domain

#### Messages

##### DataColumnSidecarByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecar_by_root/1/`

*[New in Deneb:EIP4844]*

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `PEERDAS_FORK_VERSION`     | `peerdas.DataColumnSidecar`           |

Request Content:

```
(
  DataColumnIdentifier
)
```

Response Content:

```
(
  DataColumnSidecar
)
```

The response is the column as `get_data_column_sidecar(signed_block: SignedBeaconBlock, blobs: Sequence[blobs])` computed.
