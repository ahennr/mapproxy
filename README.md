Seed via rest:

```json
{
    "seedConfig": {
        "seeds": {
            "rlp": {
                "caches": [
                    "rlp_cache"
                ],
                "refresh_before": {
                    "minutes": 1
                },
                "levels": [
                    0,
                    1,
                    2
                ]
            }
        }
    },
    "config": {
        "dry_run": false,
        "concurrency": 5,
        "geom_levels": false
    }
}
```

start server with: `mapproxy-util serve-seed-endpoint -b 4711 /path/to/mapproxy.yaml`
