# Peer Data Availability Sampling -- Networking

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in PeerDAS](#modifications-in-peerdas)
  - [Custom types](#custom-types)
  - [Preset](#preset)
  - [Containers](#containers)
    - [`DataLine`](#dataline)
    - [`DataLineSidecar`](#datalinesidecar)
  - [Helpers](#helpers)
      - [`verify_data_line_sidecar_inclusion_proof`](#verify_data_line_sidecar_inclusion_proof)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Samples subnets](#samples-subnets)
        - [`data_line_row_{line_index}`](#data_line_row_line_index)
        - [`data_line_column_{line_index}`](#data_line_column_line_index)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [GetCustodyStatus v1](#getcustodystatus-v1)
      - [DASQuery v1](#dasquery-v1)
      - [DataLineQuery v1](#datalinequery-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in PeerDAS

### Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `DataLine`   | `ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB]` | The data of each row or column in PeerDAS |

### Preset

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `KZG_COMMITMENTS_INCLUSION_PROOF_INDEX`   | `uint64(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'))` (= 27) | <!-- predefined --> Merkle proof index for `blob_kzg_commitments` |


### Containers

#### `DataLine`

```python
class SlotDataLine(Container):
    slot: Slot
    data: DataLine
```

#### `DataLineSidecar`

```python
class DataLineSidecar(Container):
    start: BlobIndex
    blobs: List[Blob, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]  # All KZGCommitment in BeaconBlock
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitments_inclusion_proof: Vector[Bytes32, floorlog2(KZG_COMMITMENTS_INCLUSION_PROOF_INDEX)]
```

### Helpers

##### `verify_data_line_sidecar_inclusion_proof`

```python
def verify_data_line_sidecar_inclusion_proof(data_line_sidecar: DataLineSidecar) -> bool:
    for i, blob in enumerate(data_line_sidecar.blobs):
        assert blob_to_kzg_commitment(blob) == data_line_sidecar.kzg_commitments[start + i]
 
    return is_valid_merkle_branch(
        leaf=hash_tree_root(data_line_sidecar.kzg_commitments),
        branch=data_line_sidecar.kzg_commitments_inclusion_proof,
        depth=floorlog2(KZG_COMMITMENTS_INCLUSION_PROOF_INDEX),
        index=KZG_COMMITMENTS_INCLUSION_PROOF_INDEX,
        root=data_line_sidecar.signed_block_header.message.body_root,
    )
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Pe to support upgraded types.

#### Topics and messages

##### Samples subnets

###### `data_line_row_{line_index}`

This topic is used to propagate the row data line, where `line_index` maps to the index of the given column.

The *type* of the payload of this topic is `DataLineSidecar`. It contains extra fields for verifying if the blob(s) of the row is included in the given `BeaconBlockHeader` with Merkle-proof.

TODO: add verification rules

###### `data_line_column_{line_index}`

This topic is used to propagate the column data line, where `line_index` maps the index of the given column.

The *type* of the payload of this topic is `SlotDataLine`.

TODO: add verification rules

### The Req/Resp domain

#### Messages

##### GetCustodyStatus v1

**Protocol ID:** `/eth2/beacon_chain/req/get_custody_status/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

Request Content:
```
(
  slot: Slot
)
```

Response Content:
```
(
  Bitvector[NUMBER_OF_ROWS * NUMBER_OF_COLUMNS]
)
```

The response bitfield indicates the samples of the given slot that the peer has and can provide.

##### DASQuery v1

**Protocol ID:** `/eth2/beacon_chain/req/das_query/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

Request Content:
```
(
  slot: Slot
  sample_index: uint64
)
```

`sample_index` maps the the index of the chunk in whole data in the flattened format (one-dimension).

Response Content:
```
(
  ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 2 // (NUMBER_OF_ROWS * NUMBER_OF_COLUMNS)]
)
```

##### DataLineQuery v1

**Protocol ID:** `/eth2/beacon_chain/req/data_line_query/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `PEERDAS_FORK_VERSION`   | `peerdas.DataLine`           |

Request Content:
```
(
  slot: Slot
  line_type: uint64
  line_index: uint64
)
```

`line_type` may be `0` for row or `1` for column; `line_index` maps the the index of the given row or column.

Response Content:
```
(
  DataLine
)
```
