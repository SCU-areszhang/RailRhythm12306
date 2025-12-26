import re
from concurrent.futures import ThreadPoolExecutor

import main

from favorites import prioritize_favorites
from inventory_sync import InventorySyncValidator


def _get_route(train_code):
    train_no = main.no_list[train_code]
    return main.train_list[train_no]


def test_train_query_route_accuracy():
    g35_route = _get_route("G35")
    g33_route = _get_route("G33")

    assert len(g35_route) == 5
    assert len(g33_route) == 7

    jinan_west = g35_route[1]
    assert jinan_west["station_name"] == "济南西"
    assert jinan_west["arrive_time"] == "11:19"
    assert jinan_west["start_time"] == "11:21"
    assert jinan_west["stop_time"] == 2

    hangzhou_east = g33_route[3]
    assert hangzhou_east["station_name"] == "杭州东"
    assert hangzhou_east["arrive_time"] == "13:24"
    assert hangzhou_east["start_time"] == "13:28"
    assert hangzhou_east["stop_time"] == 4


def test_schedule_table_rendering_formatting(capsys):
    route = _get_route("G33")
    main.print_train(route)
    output = capsys.readouterr().out

    assert "G33" in output
    assert "北京南" in output
    assert "温州南" in output
    assert re.search(r"温州南\s+15:29\s+----", output)


def test_personalized_dashboard_prioritization():
    favorites = ["G33", "G39"]
    candidates = ["G151", "G39", "G33", "G120"]
    result = prioritize_favorites(favorites, candidates)
    assert result[:2] == ["G33", "G39"]
    assert result[2:] == ["G151", "G120"]


def test_search_interaction_feedback(capsys):
    callback = main.search_link(["北京南"], ["杭州东"])
    output = capsys.readouterr().out
    assert any(code.endswith("G33") for code in callback.values())
    assert "北京南" in output
    assert "杭州东" in output
    assert re.search(r"G33.*<\s+4:28\s+>", output)


def test_inventory_sync_consistency():
    redis_data = {"G33": 45}
    db_data = {"G33": 45}
    validator = InventorySyncValidator(
        redis_reader=lambda train_id: redis_data[train_id],
        db_reader=lambda train_id: db_data[train_id],
        latency_provider=lambda: 120,
    )
    report = validator.perform_cross_check("G33")
    assert report.redis_value == report.db_value
    assert report.sync_latency_ms < 500


def test_time_interval_stress():
    for _ in range(2000):
        assert main.time_interval("08:56", "13:24") == 268


def test_high_concurrency_time_interval():
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(main.time_interval, "11:19", "11:21") for _ in range(100)]
    assert all(f.result() == 2 for f in futures)
