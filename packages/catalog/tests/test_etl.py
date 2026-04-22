from catalog.etl import enrich_records, load_sample_fixture


def test_enrich_sample_fixture() -> None:
    raw = load_sample_fixture()
    records = enrich_records(raw)
    by_title = {r.title: r for r in records}
    assert by_title["Wireless Headphones"].sku == "wh-001"
    assert by_title["Black Running Sneakers"].sku == "snk-blk-01"
    assert [r.title for r in records] == sorted(
        [r.title for r in records], key=str.casefold
    )
