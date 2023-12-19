from eth2spec.test.context import (
    expect_assertion_error,
    spec_test,
    single_phase,
    with_peerdas_and_later,
)


@with_peerdas_and_later
@spec_test
@single_phase
def test_get_custody_lines_peers_within_number_of_columns(spec):
    epoch = 1
    peer_count = 10
    custody_size = spec.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS > peer_count
    assignments = [spec.get_custody_lines(node_id, epoch, custody_size) for node_id in range(peer_count)]

    for assignment in assignments:
        assert len(assignment) == custody_size


@with_peerdas_and_later
@spec_test
@single_phase
def test_get_custody_lines_peers_more_than_number_of_columns(spec):
    epoch = 1
    peer_count = 200
    custody_size = spec.CUSTODY_REQUIREMENT
    assert spec.NUMBER_OF_COLUMNS < peer_count
    assignments = [spec.get_custody_lines(node_id, epoch, custody_size) for node_id in range(peer_count)]

    for assingment in assignments:
        assert len(assingment) == custody_size


@with_peerdas_and_later
@spec_test
@single_phase
def test_get_custody_lines_custody_size_more_than_number_of_columns(spec):
    node_id = 1
    epoch = 1
    custody_size = spec.NUMBER_OF_COLUMNS + 1
    expect_assertion_error(lambda: spec.get_custody_lines(node_id, epoch, custody_size))
