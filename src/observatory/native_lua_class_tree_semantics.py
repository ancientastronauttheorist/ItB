"""Independent bounded tree-copy semantics for the native class mutation loop.

This models only the tree phase of owner 0x002eb140: visit source entries in
key order, ensure each destination key exists, then overwrite its payload.
It makes no claim about native frames, allocation, vector append or exceptions.
"""

from __future__ import annotations
import copy
from src.observatory import native_tree_balancing_semantics as balancing


class TransferError(RuntimeError):
    pass


def validate_state(state):
    if type(state) is not dict or set(state) != {"tree", "payloads"}:
        raise TransferError("tree/payload state schema differs")
    checked = balancing.validate_tree(state["tree"])
    payloads = state["payloads"]
    if type(payloads) is not list or len(payloads) != checked["nodes"]:
        raise TransferError("payload membership differs")
    if any(type(p) is not int or not 0 <= p < 2**32 for p in payloads):
        raise TransferError("payload must be uint32")
    return checked


def transfer(source, destination):
    """Return a new destination and ordered copy records; inputs stay immutable."""
    source_order = validate_state(source)["inorder"]
    validate_state(destination)
    source_ids = {n["key"]: i for i, n in enumerate(source["tree"]["nodes"])}
    source_keys = set(source_ids)
    dest_ids = {n["key"]: i for i, n in enumerate(destination["tree"]["nodes"])}
    if len(source_keys | set(dest_ids)) > balancing.MAX_NODES:
        raise TransferError("destination union exceeds model bound")
    result = copy.deepcopy(destination)
    copies = []
    for key in source_order:
        source_id = source_ids[key]
        inserted = key not in dest_ids
        if inserted:
            dest_ids[key] = len(result["tree"]["nodes"])
            result["tree"] = balancing.insert(result["tree"], key)["tree"]
            result["payloads"].append(0)
        destination_id = dest_ids[key]
        value = source["payloads"][source_id]
        result["payloads"][destination_id] = value
        copies.append(
            dict(
                source=source_id,
                destination=destination_id,
                key=key,
                inserted=inserted,
                payload=value,
            )
        )
    validate_state(result)
    return dict(destination=result, copies=copies)
