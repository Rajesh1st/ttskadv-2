from policy import filter_items, limit_posts, rule_for


def test_selected_quality_for_movies_and_series():
    rule = {"quality_mode": "selected", "qualities": ["1080p"], "series_quality_mode": "selected", "series_qualities": ["720p"], "unknown_quality": "reject"}
    items = [{"title": "Movie 1080p", "link": "a"}, {"title": "Movie 720p", "link": "b"}, {"title": "Show S01 720p", "link": "c"}]
    allowed, rejected = filter_items(items, rule)
    assert [x["link"] for x in allowed] == ["a", "c"]
    assert len(rejected) == 1


def test_file_and_zip_limits():
    rule = {"max_file_size_mb": 10000, "max_zip_size_gb": 4}
    items = [{"title": "movie", "link": "a", "size_mb": 3000}, {"title": "archive.zip", "link": "b", "size_mb": 5000}, {"title": "movie", "link": "c", "size_mb": 11000}]
    allowed, rejected = filter_items(items, rule)
    assert [x["link"] for x in allowed] == ["a"]
    assert {reason for _, reason in rejected} == {"zip_size", "file_size"}


def test_post_limit():
    assert len(limit_posts([1, 2, 3], {"max_posts_per_cycle": 2})) == 2
    assert len(limit_posts([1, 2, 3], {"max_posts_per_cycle": 0})) == 3


def test_rule_override():
    cfg = {"posting_rules": {"ff": {"max_file_size_mb": 4096}}, "chat_overrides": {"-1": {"posting_rules": {"ff": {"max_file_size_mb": 1024}}}}}
    assert rule_for(cfg, "ff", -1)["max_file_size_mb"] == 1024


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
