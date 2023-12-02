# Peer Data Availability Sampling -- Core

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Data size](#data-size)
  - [Custody setting](#custody-setting)
  - [Helper functions](#helper-functions)
    - [`LineType`](#linetype)
    - [`get_custody_lines`](#get_custody_lines)
    - [`compute_extended_data`](#compute_extended_data)
    - [`compute_extended_matrix`](#compute_extended_matrix)
    - [`get_data_column_sidecar`](#get_data_column_sidecar)
- [Custody](#custody)
  - [Custody requirement](#custody-requirement)
  - [Public, deterministic selection](#public-deterministic-selection)
- [Peer discovery](#peer-discovery)
- [Entended data](#entended-data)
- [Row/Column gossip](#rowcolumn-gossip)
  - [Parameters](#parameters)
  - [Reconstruction and cross-seeding](#reconstruction-and-cross-seeding)
- [Peer sampling](#peer-sampling)
- [Peer scoring](#peer-scoring)
- [DAS providers](#das-providers)
- [A note on fork choice](#a-note-on-fork-choice)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `DataCell`     | `ByteList[BYTES_PER_BLOB * 2 // NUMBER_OF_COLUMNS]` | The data unit of extended data matrix |
| `DataColumn`   | `List[DataCell, MAX_BLOBS_PER_BLOCK]` | The data of each column in PeerDAS |
| `ExtendedMatrix` | `List[DataCell, MAX_BLOBS_PER_BLOCK * NUMBER_OF_COLUMNS]` | The full data with blobs and one-dimension erasure coding extension |
| `FlattenExtendedMatrix` | `ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 2]` | The flatten format of `ExtendedMatrix` |
| `LineIndex`    | `uint64` | The index of the rows or columns in `FlattenExtendedMatrix` matrix |

## Configuration

### Data size

| Name | Value | Description |
| - | - | - |
| `NUMBER_OF_COLUMNS` | `uint64(2**4)` (= 32) | Number of columns in the extended data matrix. Invariant: `assert BYTES_PER_BLOB * 2 % NUMBER_OF_COLUMNS == 0` |

### Custody setting

| Name | Value | Description |
| - | - | - |
| `SAMPLES_PER_SLOT` | `70` | Number of random samples a node queries per slot |
| `CUSTODY_REQUIREMENT` | `2` | Minimum number of both rows and columns an honest node custodies and serves samples from |
| `TARGET_NUMBER_OF_PEERS` | `70` | Suggested minimum peer count |

### Helper functions

#### `LineType`

It is implementation-dependent helpers for distinguishing the rows and columns in the following helpers.  

```python
class LineType(enum.Enum):
    ROW = 0
    COLUMN = 1
```

#### `get_custody_lines`

```python
def get_custody_lines(node_id: int, epoch: int, custody_size: int, line_type: LineType) -> list[int]:
    bound = MAX_BLOBS_PER_BLOCK if line_type else NUMBER_OF_COLUMNS
    all_items = list(range(bound))
    assert custody_size <= len(all_items)
    line_index = (node_id + epoch) % bound
    return [all_items[(line_index + i) % len(all_items)] for i in range(custody_size)]
```

#### `compute_extended_data`

```python
def compute_extended_data(data: Sequence[BLSFieldElement]) -> Sequence[BLSFieldElement]:
    # TODO
    ...
```

#### `compute_extended_matrix`

```python
def compute_extended_matrix(blobs: Sequence[Blob]) -> FlattenExtendedMatrix:
    matrix = bytearray()
    for blob in blobs:
        matrix.extend(compute_extended_data(blob))
    return FlattenExtendedMatrix(matrix)
```

#### `get_data_column_sidecar`

```python
def get_data_column_sidecar(signed_block: SignedBeaconBlock, blobs: Sequence[blobs]) -> DataColumnSidecar:
    # Compute `DataColumn` from blobs
    column = []
    column_width = BYTES_PER_BLOB * 2 // NUMBER_OF_COLUMNS
    for blob_index, blob in enumerate(blobs):
        extended_blob = compute_extended_data(blob)
        start = blob_index * NUMBER_OF_COLUMNS + column_index
        column.append(DataCell(extended_blob[start:start + column_width]))

    # Compute proofs from blobs
    # The given `block.body.blob_kzg_commitments` should have been verified as `blob_to_kzg_commitment(blob)` results
    kzg_proofs = [
        compute_blob_kzg_proof(blob, block.body.blob_kzg_commitments[blob_index])
        for blob_index, blob in enumerate(blobs)
    ]
    signed_block_header = compute_signed_block_header(signed_block)
    return DataColumnSidecar(
        index=index,
        column=DataColumn(column),
        kzg_commitments=block.body.blob_kzg_commitments,
        kzg_proofs=kzg_proofs,
        signed_block_header=signed_block_header
        kzg_commitment_merkle_proof=compute_merkle_proof(
            block.body,
            get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'),
        ),
    )
```

## Custody

### Custody requirement

Each node downloads and custodies a minimum of `CUSTODY_REQUIREMENT` rows and `CUSTODY_REQUIREMENT` columns per slot. The particular rows and columns that the node is required to custody are selected pseudo-randomly (more on this below).

A node *may* choose to custody and serve more than the minimum honesty requirement. Such a node explicitly advertises a number greater than `CUSTODY_REQUIREMENT`  via the peer discovery mechanism -- for example, in their ENR (e.g. `custody_lines: 8` if the node custodies `8` rows and `8` columns each slot) -- up to a maximum of `max(MAX_BLOBS_PER_BLOCK, NUMBER_OF_COLUMNS)` (i.e. a super-full node).

A node stores the custodied rows/columns for the duration of the pruning period and responds to peer requests for samples on those rows/columns.

### Public, deterministic selection 

The particular rows and columns that a node custodies are selected pseudo-randomly as a function (`get_custody_lines`) of the node-id, epoch, and custody size -- importantly this function can be run by any party as the inputs are all public.

*Note*: increasing the `custody_size` parameter for a given `node_id` and `epoch` extends the returned list (rather than being an entirely new shuffle) such that if `custody_size` is unknown, the default `CUSTODY_REQUIREMENT` will be correct for a subset of the node's custody.

*Note*: Even though this function accepts `epoch` as an input, the function can be tuned to remain stable for many epochs depending on network/subnet stability requirements. There is a trade-off between the rigidity of the network and the depth to which a subnet can be utilized for recovery. To ensure subnets can be utilized for recovery, staggered rotation likely needs to happen on the order of the pruning period.

## Peer discovery

At each slot, a node needs to be able to readily sample from *any* set of rows and columns. To this end, a node should find and maintain a set of diverse and reliable peers that can regularly satisfy their sampling demands.

A node runs a background peer discovery process, maintaining at least `TARGET_NUMBER_OF_PEERS` of various custody distributions (both custody_size and row/column assignments). The combination of advertised `custody_size` size and public node-id make this readily and publicly accessible.

`TARGET_NUMBER_OF_PEERS` should be tuned upward in the event of failed sampling.

*Note*: while high-capacity and super-full nodes are high value with respect to satisfying sampling requirements, a node should maintain a distribution across node capacities as to not centralize the p2p graph too much (in the extreme becomes hub/spoke) and to distribute sampling load better across all nodes.

*Note*: A DHT-based peer discovery mechanism is expected to be utilized in the above. The beacon-chain network currently utilizes discv5 in a similar method as described for finding peers of particular distributions of attestation subnets. Additional peer discovery methods are valuable to integrate (e.g., latent peer discovery via libp2p gossipsub) to add a defense in breadth against one of the discovery methods being attacked.

## Entended data

In this construction, we entend the blobs using one-dimension erasure coding extension. The matrix comprises maximum `MAX_BLOBS_PER_BLOCK` rows and fixed `NUMBER_OF_COLUMNS` columns, with each row containing a `Blob` and its corresponding extension.

## Row/Column gossip

### Parameters

1. For each row -- use `blob_sidecar_{subnet_id}` subnets, where each blob index maps to the `subnet_id`.
2. For each column -- use `data_column_sidecar_{subnet_id}` subnets, where each column index maps to the `subnet_id`. The sidecar can be computed with `get_data_column_sidecar(signed_block: SignedBeaconBlock, blobs: Sequence[blobs])` helper.

To custody a particular row or column, a node joins the respective gossip subnet. Verifiable samples from their respective row/column are gossiped on the assigned subnet.

### Reconstruction and cross-seeding

In the event a node does *not* receive all samples for a given row/column but does receive enough to reconstruct (e.g., 50%+, a function of coding rate), the node should reconstruct locally and send the reconstructed samples on the subnet.

Additionally, the node should send (cross-seed) any samples missing from a given row/column they are assigned to that they have obtained via an alternative method (ancillary gossip or reconstruction). E.g., if the node reconstructs `row_x` and is also participating in the `column_y` subnet in which the `(x, y)` sample was missing, send the reconstructed sample to `column_y`.

*Note*: A node always maintains a matrix view of the rows and columns they are following, able to cross-reference and cross-seed in either direction.

*Note*: There are timing considerations to analyze -- at what point does a node consider samples missing and choose to reconstruct and cross-seed.

*Note*: There may be anti-DoS and quality-of-service considerations around how to send samples and consider samples -- is each individual sample a message or are they sent in aggregate forms.

## Peer sampling

At each slot, a node makes (locally randomly determined) `SAMPLES_PER_SLOT` queries for samples from their peers via `DataColumnSidecarByRoot` request. A node utilizes `get_custody_lines(..., line_type=LineType.ROW)`/`get_custody_lines(..., line_type=LineType.COLUMN)` to determine which peer(s) to request from. If a node has enough good/honest peers across all rows and columns, this has a high chance of success.

## Peer scoring

Due to the deterministic custody functions, a node knows exactly what a peer should be able to respond to. In the event that a peer does not respond to samples of their custodied rows/columns, a node may downscore or disconnect from a peer.

## DAS providers

A DAS provider is a consistently-available-for-DAS-queries, super-full (or high capacity) node. To the p2p, these look just like other nodes but with high advertised capacity, and they should generally be able to be latently found via normal discovery.

They can also be found out-of-band and configured into a node to connect to directly and prioritize. For example, some L2 DAO might support 10 super-full nodes as a public good, and nodes could choose to add some set of these to their local configuration to bolster their DAS quality of service.

Such direct peering utilizes a feature supported out of the box today on all nodes and can complement (and reduce attackability) alternative peer discovery mechanisms.

## A note on fork choice

The fork choice rule (essentially a DA filter) is *orthogonal to a given DAS design*, other than the efficiency of a particular design impacting it.

In any DAS design, there are probably a few degrees of freedom around timing, acceptability of short-term re-orgs, etc. 

For example, the fork choice rule might require validators to do successful DAS on slot N to be able to include block of slot `N` in its fork choice. That's the tightest DA filter. But trailing filters are also probably acceptable, knowing that there might be some failures/short re-orgs but that they don't hurt the aggregate security. For example, the rule could be — DAS must be completed for slot N-1 for a child block in N to be included in the fork choice.

Such trailing techniques and their analysis will be valuable for any DAS construction. The question is — can you relax how quickly you need to do DA and in the worst case not confirm unavailable data via attestations/finality, and what impact does it have on short-term re-orgs and fast confirmation rules.
