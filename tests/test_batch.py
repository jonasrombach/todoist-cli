from todoist_cli.batch import BatchCommand, build_batch_payload, map_temp_ids


def test_build_batch_payload_adds_uuid_and_temp_ids():
    payload = build_batch_payload(
        [
            BatchCommand(type="item_add", args={"content": "A"}, temp_id="tmp1"),
            BatchCommand(type="item_update", args={"id": "$tmp1", "content": "B"}),
        ]
    )

    assert payload["commands"][0]["type"] == "item_add"
    assert payload["commands"][0]["temp_id"] == "tmp1"
    assert payload["commands"][0]["uuid"]
    assert payload["commands"][1]["args"]["id"] == "$tmp1"


def test_map_temp_ids_rewrites_follow_up_arguments():
    commands = [BatchCommand(type="item_update", args={"id": "$tmp1", "content": "B"})]

    mapped = map_temp_ids(commands, {"tmp1": "real1"})

    assert mapped[0].args["id"] == "real1"
