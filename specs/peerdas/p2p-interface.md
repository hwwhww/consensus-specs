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
    - [`DataColumnSidecar`](#datacolumnsidecar)
  - [Helpers](#helpers)
      - [`get_row`](#get_row)
      - [`get_column`](#get_column)
      - [`verify_column_sidecar`](#verify_column_sidecar)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Samples subnets](#samples-subnets)
        - [`data_column_{subnet_id}`](#data_column_subnet_id)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [DataRowByRootAndIndex v1](#datarowbyrootandindex-v1)
      - [DataColumnByRootAndIndex v1](#datacolumnbyrootandindex-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in PeerDAS

### Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `ExtendedData` | `ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 2]` | The full data with blobs and 1-D erasure coding extension |
| `DataRow`      | `ByteList[BYTES_PER_BLOB * 2]` | The data of each row in PeerDAS |
| `DataCell`     | `ByteList[BYTES_PER_BLOB * 2 // NUMBER_OF_COLUMNS]` | The data unit of extended data matrix |
| `DataColumn`   | `List[DataCell, MAX_BLOBS_PER_BLOCK]` | The data of each column in PeerDAS |
| `LineIndex`    | `uint64` | The index of the rows or columns in `ExtendedData` matrix |

### Preset

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `KZG_COMMITMENTS_MERKLE_PROOF_INDEX`   | `uint64(get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'))` (= 27) | <!-- predefined --> Merkle proof index for `blob_kzg_commitments` |

### Containers

#### `DataColumnSidecar`

```python
class DataColumnSidecar(Container):
    index: LineIndex  # Index of column in extended data
    column: DataColumn
    kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    kzg_proofs: List[KZGProof, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    signed_block_header: SignedBeaconBlockHeader
    kzg_commitment_merkle_proof: Vector[Bytes32, KZG_COMMITMENT_INCLUSION_PROOF_DEPTH]
```


### Helpers

##### `get_row`

```python
def get_row(data: ExtendedData, index: LineIndex) -> DataRow:
    length = BYTES_PER_BLOB * 2
    assert len(data) % (BYTES_PER_BLOB * 2) == 0
    assert len(data) // (BYTES_PER_BLOB * 2) <= MAX_BLOBS_PER_BLOCK
    return data[index * length:(index + 1) * length]
```

##### `get_column`

```python
def get_column(data: ExtendedData, index: LineIndex) -> DataColumn:
    assert len(data) % NUMBER_OF_COLUMNS == 0
    row_count = len(data) // NUMBER_OF_COLUMNS
    column_width = BYTES_PER_BLOB * 2 // NUMBER_OF_COLUMNS
    column = []
    for row_index in range(row_count):
        start = row_index * NUMBER_OF_COLUMNS + column_index
        column.append(DataCell(data[start:start + column_width]))
    return DataColumn(column)
```

##### `verify_column_sidecar`

```python
def verify_column_sidecar(sidecar: DataColumnSidecar) -> bool:
    column = sidecar.column
    column_width = BYTES_PER_BLOB * 2 // NUMBER_OF_COLUMNS
    cell_count = len(column) // column_width
    cells = [column[i * column_width:(i + 1) * column_width] for i in range(cell_count)]

    assert len(cells) == len(sidecar.kzg_commitments) == len(sidecar.kzg_proofs)
    # KZG batch verify the cells match the corresponding commitments and proofs
    assert verify_cells(cells, sidecar.index, sidecar.kzg_commitments, sidecar.kzg_proofs)
    # Verify if it's included in the beacon block
    return is_valid_merkle_branch(
        leaf=hash_tree_root(data_line_sidecar.kzg_commitments),
        branch=data_line_sidecar.kzg_commitments_merkle_proof,
        depth=floorlog2(KZG_COMMITMENTS_MERKLE_PROOF_INDEX),
        index=KZG_COMMITMENTS_MERKLE_PROOF_INDEX,
        root=data_line_sidecar.signed_block_header.message.body_root,
    )
```

TODO: define `verify_cells` helper.

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Pe to support upgraded types.

#### Topics and messages

##### Samples subnets

###### `data_column_{subnet_id}`

This topic is used to propagate column sidecars, where each column maps to some `subnet_id`.

The *type* of the payload of this topic is `DataColumn`.

TODO: add verification rules. Verify with `verify_column_sidecar`.

### The Req/Resp domain

#### Messages

##### DataRowByRootAndIndex v1

**Protocol ID:** `/eth2/beacon_chain/req/data_row_by_root_and_index/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

Request Content:
```
(
  block_root: Root
  index: LineIndex
)
```

`index` maps the the row index of the extened data.

Response Content:
```
(
  DataRow
)
```

The response is the row as `get_row(data: ExtendedData, index: LineIndex)` computed.

##### DataColumnByRootAndIndex v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_by_root_and_index/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

Request Content:
```
(
  block_root: Root
  index: LineIndex
)
```

`index` maps the the column index of the extened data.

Response Content:
```
(
  DataColumn
)
```

The response is the column as `get_column(data: ExtendedData, index: LineIndex)` computed.
