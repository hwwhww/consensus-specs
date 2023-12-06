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
    - [`get_custody_lines`](#get_custody_lines)
    - [`compute_extended_data`](#compute_extended_data)
    - [`compute_extended_matrix`](#compute_extended_matrix)
    - [`compute_samples_and_proofs`](#compute_samples_and_proofs)
    - [`get_data_column_sidecars`](#get_data_column_sidecars)
- [Custody](#custody)
  - [Custody requirement](#custody-requirement)
  - [Public, deterministic selection](#public-deterministic-selection)
- [Peer discovery](#peer-discovery)
- [Extended data](#extended-data)
- [Column gossip](#column-gossip)
  - [Parameters](#parameters)
  - [Reconstruction and cross-seeding](#reconstruction-and-cross-seeding)
- [Peer sampling](#peer-sampling)
- [Peer scoring](#peer-scoring)
- [DAS providers](#das-providers)
- [A note on fork choice](#a-note-on-fork-choice)
- [FAQs](#faqs)
  - [Row (blob) custody](#row-blob-custody)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `DataCell`     | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]` | The data unit of a cell in the extended data matrix |
| `DataColumn`   | `List[DataCell, MAX_BLOBS_PER_BLOCK]` | The data of each column in PeerDAS |
| `ExtendedMatrix` | `List[DataCell, MAX_BLOBS_PER_BLOCK * NUMBER_OF_COLUMNS]` | The full data with blobs and one-dimension erasure coding extension |
| `FlattenExtendedMatrix` | `List[BLSFieldElement, MAX_BLOBS_PER_BLOCK * FIELD_ELEMENTS_PER_BLOB * 2 * NUMBER_OF_COLUMNS]` | The flatten format of `ExtendedMatrix` |
| `LineIndex`    | `uint64` | The index of the rows or columns in `FlattenExtendedMatrix` matrix |

## Configuration

### Data size

| Name | Value | Description |
| - | - | - |
| `NUMBER_OF_COLUMNS` | `uint64(2**6)` (= 32) | Number of columns in the extended data matrix. Invariant: `assert FIELD_ELEMENTS_PER_BLOB * 2 % NUMBER_OF_COLUMNS == 0` |
| `FIELD_ELEMENTS_PER_CELL` | `FIELD_ELEMENTS_PER_BLOB * 2 // NUMBER_OF_COLUMNS` | Elements per `DataCell` |

### Custody setting

| Name | Value | Description |
| - | - | - |
| `SAMPLES_PER_SLOT` | `70` | Number of random samples a node queries per slot |
| `CUSTODY_REQUIREMENT` | `2` | Minimum number columns an honest node custodies and serves samples from |
| `TARGET_NUMBER_OF_PEERS` | `70` | Suggested minimum peer count |

### Helper functions

#### `get_custody_lines`

```python
def get_custody_lines(node_id: NodeID, epoch: Epoch, custody_size: uint64) -> Sequence[LineIndex]:
    assert custody_size <= MAX_BLOBS_PER_BLOCK
    all_items = list(range(MAX_BLOBS_PER_BLOCK))
    line_index = (node_id + epoch) % MAX_BLOBS_PER_BLOCK
    return [LineIndex(all_items[(line_index + i) % len(all_items)]) for i in range(custody_size)]
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
    matrix = [compute_extended_data(blob) for blob in blobs]
    return FlattenExtendedMatrix(matrix)
```

#### `compute_samples_and_proofs`

```python
def compute_samples_and_proofs(blob: Blob) -> Tuple[
        Vector[DataCell, NUMBER_OF_COLUMNS * 2],
        Vector[KZGProof, NUMBER_OF_COLUMNS * 2]]:
    """
    Defined in polynomial-commitments-sampling.md
    """
    ...
```

#### `get_data_column_sidecars`

```python
def get_data_column_sidecars(signed_block: SignedBeaconBlock,
                             blobs: Sequence[Blob]) -> Sequence[DataColumnSidecar]:
    signed_block_header = compute_signed_block_header(signed_block)
    block = signed_block.message
    kzg_commitments_inclusion_proof = compute_merkle_proof(
        block.body,
        get_generalized_index(BeaconBlockBody, 'blob_kzg_commitments'),
    )
    cells, proofs = [compute_samples_and_proofs(blob) for blob in blobs]
    sidecars = []
    for column_index in range(NUMBER_OF_COLUMNS):
        column = DataColumn([cells[0][column_index + MAX_BLOBS_PER_BLOCK * i]
                             for i in range(MAX_BLOBS_PER_BLOCK)])
        kzg_proof_of_column = [proofs[1][column_index + MAX_BLOBS_PER_BLOCK * i]
                               for i in range(MAX_BLOBS_PER_BLOCK)]
        sidecars.append(DataColumnSidecar(
            index=column_index,
            column=column,
            kzg_commitments=block.body.blob_kzg_commitments,
            kzg_proofs=kzg_proof_of_column,
            signed_block_header=signed_block_header,
            kzg_commitments_inclusion_proof=kzg_commitments_inclusion_proof,
        ))
    return sidecars
```

## Custody

### Custody requirement

Each node downloads and custodies a minimum of `CUSTODY_REQUIREMENT` columns per slot. The particular columns that the node is required to custody are selected pseudo-randomly (more on this below).

A node *may* choose to custody and serve more than the minimum honesty requirement. Such a node explicitly advertises a number greater than `CUSTODY_REQUIREMENT`  via the peer discovery mechanism -- for example, in their ENR (e.g. `custody_lines: 8` if the node custodies `8` columns each slot) -- up to a `NUMBER_OF_COLUMNS` (i.e. a super-full node).

A node stores the custodied columns for the duration of the pruning period and responds to peer requests for samples on those columns.

### Public, deterministic selection 

The particular columns that a node custodies are selected pseudo-randomly as a function (`get_custody_lines`) of the node-id, epoch, and custody size -- importantly this function can be run by any party as the inputs are all public.

*Note*: increasing the `custody_size` parameter for a given `node_id` and `epoch` extends the returned list (rather than being an entirely new shuffle) such that if `custody_size` is unknown, the default `CUSTODY_REQUIREMENT` will be correct for a subset of the node's custody.

*Note*: Even though this function accepts `epoch` as an input, the function can be tuned to remain stable for many epochs depending on network/subnet stability requirements. There is a trade-off between the rigidity of the network and the depth to which a subnet can be utilized for recovery. To ensure subnets can be utilized for recovery, staggered rotation likely needs to happen on the order of the pruning period.

## Peer discovery

At each slot, a node needs to be able to readily sample from *any* set of columns. To this end, a node should find and maintain a set of diverse and reliable peers that can regularly satisfy their sampling demands.

A node runs a background peer discovery process, maintaining at least `TARGET_NUMBER_OF_PEERS` of various custody distributions (both custody_size and column assignments). The combination of advertised `custody_size` size and public node-id make this readily and publicly accessible.

`TARGET_NUMBER_OF_PEERS` should be tuned upward in the event of failed sampling.

*Note*: while high-capacity and super-full nodes are high value with respect to satisfying sampling requirements, a node should maintain a distribution across node capacities as to not centralize the p2p graph too much (in the extreme becomes hub/spoke) and to distribute sampling load better across all nodes.

*Note*: A DHT-based peer discovery mechanism is expected to be utilized in the above. The beacon-chain network currently utilizes discv5 in a similar method as described for finding peers of particular distributions of attestation subnets. Additional peer discovery methods are valuable to integrate (e.g., latent peer discovery via libp2p gossipsub) to add a defense in breadth against one of the discovery methods being attacked.

## Extended data

In this construction, we entend the blobs using one-dimension erasure coding extension. The matrix comprises maximum `MAX_BLOBS_PER_BLOCK` rows and fixed `NUMBER_OF_COLUMNS` columns, with each row containing a `Blob` and its corresponding extension.

## Column gossip

### Parameters

For each column -- use `data_column_sidecar_{subnet_id}` subnets, where each column index maps to the `subnet_id`. The sidecars can be computed with `get_data_column_sidecars(signed_block: SignedBeaconBlock, blobs: Sequence[Blob])` helper.

To custody a particular column, a node joins the respective gossip subnet. Verifiable samples from their respective column are gossiped on the assigned subnet.

### Reconstruction and cross-seeding

If the node obtains 50%+ of all the columns, they can reconstruct the full data matrix via `recover_samples_impl` helper.

If a node fails to sample a peer or fails to get a column on the column subnet, a node can utilize the Req/Resp message to query the missing column from other peers.

Once the node obtain the column, the node should send the missing columns to the column subnets.

*Note*: A node always maintains a matrix view of the rows and columns they are following, able to cross-reference and cross-seed in either direction.

*Note*: There are timing considerations to analyze -- at what point does a node consider samples missing and choose to reconstruct and cross-seed.

*Note*: There may be anti-DoS and quality-of-service considerations around how to send samples and consider samples -- is each individual sample a message or are they sent in aggregate forms.

## Peer sampling

At each slot, a node makes (locally randomly determined) `SAMPLES_PER_SLOT` queries for samples from their peers via `DataColumnSidecarByRoot` request. A node utilizes `get_custody_lines` helper to determine which peer(s) to request from. If a node has enough good/honest peers across all rows and columns, this has a high chance of success.

## Peer scoring

Due to the deterministic custody functions, a node knows exactly what a peer should be able to respond to. In the event that a peer does not respond to samples of their custodied rows/columns, a node may downscore or disconnect from a peer.

## DAS providers

A DAS provider is a consistently-available-for-DAS-queries, super-full (or high capacity) node. To the p2p, these look just like other nodes but with high advertised capacity, and they should generally be able to be latently found via normal discovery.

DAS providers can also be found out-of-band and configured into a node to connect to directly and prioritize. Nodes can add some set of these to their local configuration for persistent connection to bolster their DAS quality of service.

Such direct peering utilizes a feature supported out of the box today on all nodes and can complement (and reduce attackability and increase quality-of-service) alternative peer discovery mechanisms.

## A note on fork choice

*Fork choice spec TBD, but it will just be a replacement of `is_data_available()` call in Deneb with column sampling instead of full download. Note the `is_data_available(slot_N)` will likely do a `-1` follow distance so that you just need to check the availability of slot `N-1` for slot `N` (starting with the block proposer of `N`).*

The fork choice rule (essentially a DA filter) is *orthogonal to a given DAS design*, other than the efficiency of a particular design impacting it.

In any DAS design, there are probably a few degrees of freedom around timing, acceptability of short-term re-orgs, etc. 

For example, the fork choice rule might require validators to do successful DAS on slot N to be able to include block of slot `N` in its fork choice. That's the tightest DA filter. But trailing filters are also probably acceptable, knowing that there might be some failures/short re-orgs but that they don't hurt the aggregate security. For example, the rule could be — DAS must be completed for slot N-1 for a child block in N to be included in the fork choice.

Such trailing techniques and their analysis will be valuable for any DAS construction. The question is — can you relax how quickly you need to do DA and in the worst case not confirm unavailable data via attestations/finality, and what impact does it have on short-term re-orgs and fast confirmation rules.

## FAQs

### Row (blob) custody

In the one-dimension construction, a node samples the peers by requesting the whole `DataColumn`. In reconstruction, a node can reconstruct all the blobs by 50% of the columns. Note that nodes can still download the row via `blob_sidecar_{subnet_id}` subnets.

The potential benefits of having row custody could include:

1. Allow for more "natural" distribution of data to consumers -- e.g., roll-ups -- but honestly, they won't know a priori which row their blob is going to be included in in the block, so they would either need to listen to all rows or download a particular row after seeing the block. The former looks just like listening to column [0, N)  and the latter is req/resp instead of gossiping.
2. Help with some sort of distributed reconstruction. Those with full rows can compute extensions and seed missing samples to the network. This would either need to be able to send individual points on the gossip or would need some sort of req/resp faculty, potentially similar to an `IHAVEPOINTBITFIELD` and `IWANTSAMPLE`.

However, for simplicity, we don't assign row custody assignments to nodes in the current design.
