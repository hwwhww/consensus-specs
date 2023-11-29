# Peer Data Availability Sampling -- Networking

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in PeerDAS](#modifications-in-peerdas)
- [Custom types](#custom-types)
- [Containers](#containers)
    - [`DataLine`](#dataline)
    - [`CustodyStatus`](#custodystatus)
    - [`DASSample`](#dassample)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Samples subnets](#samples-subnets)
        - [`data_line_{line_type}_{line_index}`](#data_line_line_type_line_index)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [DoYouHave v1](#doyouhave-v1)
      - [DASQuery v1](#dasquery-v1)
      - [DataLineQuery v1](#datalinequery-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in PeerDAS

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `DataLine`   | `ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 4]` | The data of each row or column in PeerDAS |

**TODO**: Change PeerDAS `MAX_BLOBS_PER_BLOCK` to full-danksharding size.

## Containers

#### `DataLine`

```python
class SlotDataLine(Container):
    slot: Slot
    data: DataLine
```

#### `CustodyStatus`

```python
class CustodyStatus(Container):
    row: Bitvector[NUMBER_OF_ROWS]
    column: Bitvector[NUMBER_OF_COLUMNS]
```

#### `DASSample`

```python
class DASSample(Container):
    slot: Slot
    chunk: ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 4 // (NUMBER_OF_ROWS * NUMBER_OF_COLUMNS)]
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Deneb to support upgraded types.

#### Topics and messages

##### Samples subnets

###### `data_line_{line_type}_{line_index}`

This topic is used to propagate the data line. `line_type` may be `0` for row or `1` for column; `line_index` maps the index of the given row or column.

The *type* of the payload of this topic is `SlotDataLine`.

### The Req/Resp domain

#### Messages

##### DoYouHave v1

**Protocol ID:** `/eth2/beacon_chain/req/do_you_have/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `PEERDAS_FORK_VERSION`   | `peerdas.CustodyStatus`       |

Request Content:
```
(
  slot: Slot
)
```

Response Content:
```
(
  CustodyStatus
)
```

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
  das_sample: ByteList[MAX_BLOBS_PER_BLOCK * BYTES_PER_BLOB * 4 // (NUMBER_OF_ROWS * NUMBER_OF_COLUMNS)]
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
  data_line: DataLine
)
```
