from core_model.semantic_chunk.hierarchy import would_create_cycle


def test_assigning_no_parent_never_creates_a_cycle():
    assert would_create_cycle(1, None, parent_of=lambda _id: None) is False


def test_assigning_self_as_parent_is_a_cycle():
    assert would_create_cycle(1, 1, parent_of=lambda _id: None) is True


def test_assigning_a_descendant_as_parent_is_a_cycle():
    # chain: 3 -> 2 -> 1 (2's parent is 1, 3's parent is 2)
    parents = {2: 1, 3: 2}
    assert would_create_cycle(1, 3, parent_of=lambda cid: parents.get(cid)) is True


def test_assigning_an_unrelated_chunk_as_parent_is_fine():
    parents = {2: 1, 3: 2}
    assert would_create_cycle(4, 3, parent_of=lambda cid: parents.get(cid)) is False


def test_pre_existing_cycle_in_data_is_treated_as_unsafe_rather_than_looping_forever():
    parents = {1: 2, 2: 1}
    assert would_create_cycle(3, 1, parent_of=lambda cid: parents.get(cid)) is True
